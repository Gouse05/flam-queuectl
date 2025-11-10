#!/usr/bin/env python3
"""
queuectl.py
A minimal CLI-backed job queue system with persistent storage (SQLite),
workers, exponential backoff, DLQ support, and basic config management.

Usage examples:
  ./queuectl.py enqueue '{"id":"job1","command":"echo hello","max_retries":3}'
  ./queuectl.py worker start --count 2
  ./queuectl.py status
  ./queuectl.py list --state pending
  ./queuectl.py dlq list
  ./queuectl.py dlq retry job1
  ./queuectl.py config set backoff_base 2
"""

import os
import sys
import json
import sqlite3
import time
import subprocess
import signal
import click
import datetime
from pathlib import Path
from typing import Optional

APP_DIR = Path.home() / ".queuectl"
DB_PATH = APP_DIR / "queue.db"
PIDS_PATH = APP_DIR / "worker_pids.txt"
DEFAULT_BACKOFF_BASE = 2

# ---------- DB helpers ----------
def ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)

def get_conn():
    ensure_app_dir()
    conn = sqlite3.connect(str(DB_PATH), timeout=30, isolation_level=None)  # autocommit mode
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        command TEXT NOT NULL,
        state TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 3,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        next_run INTEGER NOT NULL DEFAULT 0,
        last_exit_code INTEGER
    );
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    # set defaults if missing
    cur.execute("INSERT OR IGNORE INTO config (key,value) VALUES ('backoff_base', ?)", (str(DEFAULT_BACKOFF_BASE),))
    conn.commit()
    conn.close()

def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def now_ts():
    return int(time.time())

# ---------- Config ----------
def config_get(key: str, default: Optional[str]=None) -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key=?", (key,))
    r = cur.fetchone()
    conn.close()
    return r["value"] if r else (default if default is not None else "")

def config_set(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO config (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()

# ---------- CLI ----------
@click.group()
def cli():
    init_db()

# ---------- Enqueue ----------
@cli.command()
@click.argument("job_json", required=True)
def enqueue(job_json):
    """queuectl enqueue '{"id":"job1","command":"sleep 2","max_retries":3}'"""
    try:
        payload = json.loads(job_json)
    except Exception as e:
        click.echo("Invalid JSON: " + str(e))
        sys.exit(1)
    required = ["id", "command"]
    for k in required:
        if k not in payload:
            click.echo(f"Missing field '{k}' in job JSON")
            sys.exit(1)
    job_id = payload["id"]
    command = payload["command"]
    max_retries = int(payload.get("max_retries", 3))
    ts_iso = now_iso()
    ts = now_ts()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO jobs (id,command,state,attempts,max_retries,created_at,updated_at,next_run) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, command, "pending", 0, max_retries, ts_iso, ts_iso, ts)
        )
        conn.commit()
        click.echo(f"Enqueued job {job_id}")
    except sqlite3.IntegrityError:
        click.echo(f"Job with id {job_id} already exists")
    finally:
        conn.close()

# ---------- Worker management ----------
def spawn_worker_process():
    """
    Launch a new background Python process to run a single worker.
    """
    cmd = [sys.executable, os.path.realpath(__file__), "worker", "run"]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.pid

@cli.group()
def worker():
    """worker start/stop commands"""
    pass

@worker.command("start")
@click.option("--count", default=1, help="Number of workers to start")
def worker_start(count):
    """Start N worker processes in background"""
    ensure_app_dir()
    pids = []
    for _ in range(count):
        pid = spawn_worker_process()
        pids.append(pid)
        click.echo(f"Started worker pid={pid}")
    # append to pids file
    with open(PIDS_PATH, "a") as f:
        for pid in pids:
            f.write(str(pid) + "\n")

@worker.command("stop")
def worker_stop():
    """Stop running workers (reads pids from file)"""
    if not PIDS_PATH.exists():
        click.echo("No worker PIDs found.")
        return
    alive = []
    with open(PIDS_PATH, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    for ln in lines:
        try:
            pid = int(ln)
            os.kill(pid, signal.SIGTERM)
            click.echo(f"Signalled pid {pid} for termination.")
        except ProcessLookupError:
            click.echo(f"pid {ln} not running.")
        except Exception as e:
            click.echo(f"Failed to signal pid {ln}: {e}")
    # remove pid file
    try:
        PIDS_PATH.unlink()
    except:
        pass

@worker.command("run")
def worker_run():
    """Internal: run a single worker loop in foreground (intended to be started by worker start)"""
    # graceful shutdown
    stop = False
    def _sigterm(signum, frame):
        nonlocal stop
        stop = True
        click.echo("Worker: graceful shutdown requested, will finish current job then exit.")
    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    click.echo("Worker started (foreground). Press Ctrl-C to stop.")
    conn = get_conn()
    cur = conn.cursor()
    while not stop:
        try:
            # Claim a pending job whose next_run <= now by performing an atomic UPDATE
            ts_now = now_ts()
            cur.execute("""
                UPDATE jobs
                SET state='processing', attempts=attempts+1, updated_at=?, next_run=?
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE state='pending' AND next_run <= ?
                    ORDER BY created_at LIMIT 1
                )
            """, (now_iso(), ts_now, ts_now))
            if cur.rowcount == 0:
                # nothing to process; sleep briefly
                time.sleep(0.8)
                continue
            # fetch the job we just took
            cur.execute("SELECT * FROM jobs WHERE state='processing' ORDER BY updated_at DESC LIMIT 1")
            job = cur.fetchone()
            if not job:
                continue
            job_id = job["id"]
            command = job["command"]
            attempts = job["attempts"]
            max_retries = job["max_retries"]
            click.echo(f"[{job_id}] Running attempt {attempts}/{max_retries}: {command}")
            # Execute the command using shell
            proc = subprocess.Popen(command, shell=True)
            while proc.poll() is None:
                if stop:
                    # wait for current process to finish before quitting
                    click.echo(f"[{job_id}] waiting for running command to finish for graceful shutdown...")
                    proc.wait()
                    break
                time.sleep(0.2)
            exit_code = proc.returncode if proc.returncode is not None else 1
            cur.execute("UPDATE jobs SET last_exit_code=?, updated_at=? WHERE id=?", (exit_code, now_iso(), job_id))
            if exit_code == 0:
                cur.execute("UPDATE jobs SET state='completed', updated_at=? WHERE id=?", (now_iso(), job_id))
                click.echo(f"[{job_id}] Completed successfully.")
            else:
                # determine backoff and schedule next run or move to dead
                if attempts > max_retries:
                    # move to dead
                    cur.execute("UPDATE jobs SET state='dead', updated_at=? WHERE id=?", (now_iso(), job_id))
                    click.echo(f"[{job_id}] Moved to DLQ (exhausted retries).")
                else:
                    # exponential backoff: delay = base ** attempts
                    base = int(config_get("backoff_base", str(DEFAULT_BACKOFF_BASE)))
                    delay = base ** attempts
                    next_run_ts = now_ts() + delay
                    cur.execute("UPDATE jobs SET state='pending', next_run=?, updated_at=? WHERE id=?", (next_run_ts, now_iso(), job_id))
                    click.echo(f"[{job_id}] Failed (exit {exit_code}). Scheduled retry in {delay}s (attempt {attempts}/{max_retries}).")
            conn.commit()
        except sqlite3.OperationalError as e:
            click.echo("DB busy, retrying... " + str(e))
            time.sleep(0.5)
        except Exception as e:
            click.echo("Worker error: " + str(e))
            time.sleep(1)
    conn.close()
    click.echo("Worker exiting.")

# ---------- Status & listing ----------
@cli.command("status")
def status():
    """Show summary of job states & active workers"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state, COUNT(*) as cnt FROM jobs GROUP BY state")
    rows = cur.fetchall()
    click.echo("Job states:")
    counts = {r["state"]: r["cnt"] for r in rows}
    for s in ["pending", "processing", "completed", "failed", "dead"]:
        click.echo(f"  {s:10} : {counts.get(s,0)}")
    # workers
    running = []
    if PIDS_PATH.exists():
        with open(PIDS_PATH, "r") as f:
            for line in f:
                ln=line.strip()
                if not ln: continue
                try:
                    pid=int(ln)
                    os.kill(pid, 0)
                    running.append(pid)
                except Exception:
                    pass
    click.echo(f"Active worker pids: {running}")
    conn.close()

@cli.command("list")
@click.option("--state", default=None, help="Filter by job state (pending,processing,completed,dead)")
def list_jobs(state):
    """List jobs; use --state pending to list only pending jobs"""
    conn = get_conn()
    cur = conn.cursor()
    if state:
        cur.execute("SELECT * FROM jobs WHERE state=? ORDER BY created_at", (state,))
    else:
        cur.execute("SELECT * FROM jobs ORDER BY created_at")
    rows = cur.fetchall()
    for r in rows:
        next_run = r["next_run"]
        nr = datetime.datetime.utcfromtimestamp(next_run).isoformat()+"Z" if next_run else "-"
        click.echo(f"{r['id']:20} {r['state']:10} attempts={r['attempts']}/{r['max_retries']} next_run={nr} cmd=\"{r['command']}\"")
    conn.close()

# ---------- DLQ ----------
@cli.group()
def dlq():
    """Dead Letter Queue management"""
    pass

@dlq.command("list")
def dlq_list():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE state='dead' ORDER BY updated_at")
    rows = cur.fetchall()
    if not rows:
        click.echo("DLQ is empty.")
    for r in rows:
        click.echo(f"{r['id']:20} last_exit={r['last_exit_code']} attempts={r['attempts']}/{r['max_retries']} cmd=\"{r['command']}\"")
    conn.close()

@dlq.command("retry")
@click.argument("job_id", required=True)
def dlq_retry(job_id):
    """Retry a DLQ job: moves job back to pending with attempts reset"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id=? AND state='dead'", (job_id,))
    r = cur.fetchone()
    if not r:
        click.echo("DLQ job not found: " + job_id)
        return
    cur.execute("UPDATE jobs SET state='pending', attempts=0, next_run=?, updated_at=? WHERE id=?", (now_ts(), now_iso(), job_id))
    conn.commit()
    conn.close()
    click.echo(f"Moved {job_id} back to pending.")

# ---------- Config ----------
@cli.group()
def config():
    """Set/get configuration values"""
    pass

@config.command("set")
@click.argument("key", required=True)
@click.argument("value", required=True)
def config_set_cmd(key, value):
    config_set(key, value)
    click.echo(f"Config {key} set to {value}")

@config.command("get")
@click.argument("key", required=True)
def config_get_cmd(key):
    v = config_get(key, "")
    click.echo(f"{key} = {v}")

# ---------- Bootstrapping: create DB ----------
if __name__ == "__main__":
    cli()
