#!/usr/bin/env python3
"""
queuectl.py
Enhanced CLI-based background job queue system (FLAM Backend Assignment)
Includes:
 - Persistent SQLite storage
 - Exponential backoff retry
 - DLQ (Dead Letter Queue)
 - Configurable retry/backoff
 - Job timeout handling
 - Priority-based scheduling
 - Delayed jobs via `run_at`
 - Job output logging
 - Metrics command
 - Windows-safe worker stop
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
import platform
from pathlib import Path
from typing import Optional

# -------------------- App Paths --------------------
APP_DIR = Path.home() / ".queuectl"
DB_PATH = APP_DIR / "queue.db"
PIDS_PATH = APP_DIR / "worker_pids.txt"
LOG_DIR = APP_DIR / "job_logs"
DEFAULT_BACKOFF_BASE = 2
DEFAULT_TIMEOUT = 30  # seconds

# -------------------- Helpers --------------------
def ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_conn():
    ensure_app_dir()
    conn = sqlite3.connect(str(DB_PATH), timeout=30, isolation_level=None)
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
        last_exit_code INTEGER,
        priority INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    cur.execute("INSERT OR IGNORE INTO config (key,value) VALUES ('backoff_base', ?)", (str(DEFAULT_BACKOFF_BASE),))
    cur.execute("INSERT OR IGNORE INTO config (key,value) VALUES ('job_timeout', ?)", (str(DEFAULT_TIMEOUT),))
    conn.commit()
    conn.close()

def now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def now_ts():
    return int(time.time())

# -------------------- Config --------------------
def config_get(key: str, default: Optional[str] = None) -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM config WHERE key=?", (key,))
    r = cur.fetchone()
    conn.close()
    return r["value"] if r else (default if default is not None else "")

def config_set(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO config (key,value)
        VALUES (?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, value))
    conn.commit()
    conn.close()

# -------------------- CLI Root --------------------
@click.group()
def cli():
    init_db()

# -------------------- Enqueue --------------------
@cli.command()
@click.argument("job_json", required=True)
def enqueue(job_json):
    """Enqueue a new job (JSON input)"""
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
    priority = int(payload.get("priority", 0))
    run_at = int(payload.get("run_at", now_ts()))  # for scheduled jobs
    ts_iso = now_iso()

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO jobs (id, command, state, attempts, max_retries,
                              created_at, updated_at, next_run, priority)
            VALUES (?, ?, 'pending', 0, ?, ?, ?, ?, ?)
        """, (job_id, command, max_retries, ts_iso, ts_iso, run_at, priority))
        conn.commit()
        click.echo(f"Enqueued job {job_id}")
    except sqlite3.IntegrityError:
        click.echo(f"Job with id {job_id} already exists")
    finally:
        conn.close()

# -------------------- Worker --------------------
def spawn_worker_process():
    cmd = [sys.executable, os.path.realpath(__file__), "worker", "run"]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return p.pid

@cli.group()
def worker():
    """Manage worker processes"""
    pass

@worker.command("start")
@click.option("--count", default=1, help="Number of workers to start")
def worker_start(count):
    ensure_app_dir()
    pids = []
    for _ in range(count):
        pid = spawn_worker_process()
        pids.append(pid)
        click.echo(f"Started worker pid={pid}")
    with open(PIDS_PATH, "a") as f:
        for pid in pids:
            f.write(str(pid) + "\n")

@worker.command("stop")
def worker_stop():
    """Stop running workers safely"""
    if not PIDS_PATH.exists():
        click.echo("No worker PIDs found.")
        return
    with open(PIDS_PATH, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    for ln in lines:
        try:
            pid = int(ln)
            if platform.system() == "Windows":
                os.system(f"taskkill /F /PID {pid} >nul 2>&1")
                click.echo(f"Stopped worker pid={pid}")
            else:
                os.kill(pid, signal.SIGTERM)
                click.echo(f"Signalled pid {pid} for termination.")
        except Exception:
            pass
    try:
        PIDS_PATH.unlink()
    except Exception:
        pass

@worker.command("run")
def worker_run():
    """Worker process loop"""
    stop = False
    def _sigterm(signum, frame):
        nonlocal stop
        stop = True
        click.echo("Worker: graceful shutdown requested.")
    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    conn = get_conn()
    cur = conn.cursor()
    while not stop:
        try:
            ts_now = now_ts()
            cur.execute("""
                UPDATE jobs
                SET state='processing', attempts=attempts+1, updated_at=?, next_run=?
                WHERE id = (
                    SELECT id FROM jobs
                    WHERE state='pending' AND next_run <= ?
                    ORDER BY priority DESC, created_at
                    LIMIT 1
                )
            """, (now_iso(), ts_now, ts_now))
            if cur.rowcount == 0:
                time.sleep(0.8)
                continue

            cur.execute("SELECT * FROM jobs WHERE state='processing' ORDER BY updated_at DESC LIMIT 1")
            job = cur.fetchone()
            if not job:
                continue

            job_id, command, attempts, max_retries = job["id"], job["command"], job["attempts"], job["max_retries"]
            log_path = LOG_DIR / f"{job_id}.log"
            timeout = int(config_get("job_timeout", str(DEFAULT_TIMEOUT)))
            click.echo(f"[{job_id}] Running attempt {attempts}/{max_retries} with timeout={timeout}s")

            with open(log_path, "w") as log_file:
                try:
                    proc = subprocess.Popen(command, shell=True, stdout=log_file, stderr=log_file)
                    proc.wait(timeout=timeout)
                    exit_code = proc.returncode
                except subprocess.TimeoutExpired:
                    proc.kill()
                    exit_code = -1
                    log_file.write("\n[TimeoutExpired] Job exceeded time limit.\n")

            cur.execute("UPDATE jobs SET last_exit_code=?, updated_at=? WHERE id=?",
                        (exit_code, now_iso(), job_id))

            if exit_code == 0:
                cur.execute("UPDATE jobs SET state='completed', updated_at=? WHERE id=?", (now_iso(), job_id))
                click.echo(f"[{job_id}] ✅ Completed successfully.")
            else:
                if attempts > max_retries:
                    cur.execute("UPDATE jobs SET state='dead', updated_at=? WHERE id=?", (now_iso(), job_id))
                    click.echo(f"[{job_id}] ☠️ Moved to DLQ (max retries reached).")
                else:
                    base = int(config_get("backoff_base", str(DEFAULT_BACKOFF_BASE)))
                    delay = base ** attempts
                    next_run_ts = now_ts() + delay
                    cur.execute("""
                        UPDATE jobs
                        SET state='pending', next_run=?, updated_at=?
                        WHERE id=?
                    """, (next_run_ts, now_iso(), job_id))
                    click.echo(f"[{job_id}] ❌ Failed (exit {exit_code}). Retry in {delay}s.")
            conn.commit()
        except Exception as e:
            click.echo(f"Worker error: {e}")
            time.sleep(1)
    conn.close()
    click.echo("Worker exiting.")

# -------------------- Status, List, Metrics --------------------
@cli.command("status")
def status():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT state, COUNT(*) as cnt FROM jobs GROUP BY state")
    rows = cur.fetchall()
    click.echo("Job states:")
    counts = {r["state"]: r["cnt"] for r in rows}
    for s in ["pending", "processing", "completed", "failed", "dead"]:
        click.echo(f"  {s:10} : {counts.get(s,0)}")
    running = []
    if PIDS_PATH.exists():
        with open(PIDS_PATH, "r") as f:
            for ln in f:
                try:
                    pid = int(ln.strip())
                    os.kill(pid, 0)
                    running.append(pid)
                except Exception:
                    pass
    click.echo(f"Active worker pids: {running}")
    conn.close()

@cli.command("list")
@click.option("--state", default=None, help="Filter by state")
def list_jobs(state):
    conn = get_conn()
    cur = conn.cursor()
    if state:
        cur.execute("SELECT * FROM jobs WHERE state=? ORDER BY created_at", (state,))
    else:
        cur.execute("SELECT * FROM jobs ORDER BY created_at")
    rows = cur.fetchall()
    for r in rows:
        nr = datetime.datetime.utcfromtimestamp(r["next_run"]).isoformat()+"Z"
        click.echo(f"{r['id']:20} {r['state']:10} priority={r['priority']} attempts={r['attempts']}/{r['max_retries']} next_run={nr} cmd=\"{r['command']}\"")
    conn.close()

@cli.command("metrics")
def metrics():
    """Show basic job metrics"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jobs")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM jobs WHERE state='completed'")
    done = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM jobs WHERE state='dead'")
    dead = cur.fetchone()[0]
    success_rate = (done / total * 100) if total > 0 else 0
    click.echo(f"📊 Total jobs: {total}\n✅ Completed: {done}\n☠️ Dead: {dead}\nSuccess rate: {success_rate:.1f}%")
    conn.close()

# -------------------- DLQ --------------------
@cli.group()
def dlq():
    pass

@dlq.command("list")
def dlq_list():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE state='dead' ORDER BY updated_at")
    rows = cur.fetchall()
    if not rows:
        click.echo("DLQ is empty.")
        return
    for r in rows:
        click.echo(f"{r['id']:20} last_exit={r['last_exit_code']} attempts={r['attempts']}/{r['max_retries']} cmd=\"{r['command']}\"")
    conn.close()

@dlq.command("retry")
@click.argument("job_id", required=True)
def dlq_retry(job_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id=? AND state='dead'", (job_id,))
    r = cur.fetchone()
    if not r:
        click.echo("DLQ job not found: " + job_id)
        return
    cur.execute("UPDATE jobs SET state='pending', attempts=0, next_run=?, updated_at=? WHERE id=?",
                (now_ts(), now_iso(), job_id))
    conn.commit()
    conn.close()
    click.echo(f"Moved {job_id} back to pending.")

# -------------------- Config --------------------
@cli.group()
def config():
    pass

@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set_cmd(key, value):
    config_set(key, value)
    click.echo(f"Config {key} set to {value}")

@config.command("get")
@click.argument("key")
def config_get_cmd(key):
    v = config_get(key, "")
    click.echo(f"{key} = {v}")

# -------------------- Entry --------------------
if __name__ == "__main__":
    cli()
