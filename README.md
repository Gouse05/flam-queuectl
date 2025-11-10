# QueueCTL – Backend Developer Assignment (FLAM)

A CLI-based background job queue system built in **Python** that manages background jobs, retries failures with **exponential backoff**, and maintains a **Dead Letter Queue (DLQ)**.  
Now enhanced with **bonus features** like job timeout, priority queueing, scheduling, logging, and metrics.

---

## ⚙️ Tech Stack

- **Language:** Python 3.10  
- **Libraries:** Click (CLI), SQLite3 (standard library)  
- **Tested On:** Windows 10/11  

---

## 🎯 Objective

Build a minimal production-grade **background job queue system** that supports:

- Enqueuing and managing background jobs  
- Running multiple worker processes  
- Retrying failed jobs automatically with exponential backoff  
- Maintaining a Dead Letter Queue (DLQ)  
- Persistent job storage across restarts  
- All features accessible via CLI  

---

## ⚙️ Setup Instructions

```bash
cd flam-queuectl
python -m venv venv
venv\Scripts\activate
pip install click
python queuectl.py status
```

---

## 💻 Usage Examples (Windows CMD / PowerShell)

### Enqueue Jobs
```bash
python queuectl.py enqueue "{\"id\":\"job_ok\",\"command\":\"echo hello\",\"max_retries\":2}"
python queuectl.py enqueue "{\"id\":\"job_fail\",\"command\":\"nonexistent_cmd\",\"max_retries\":2}"
```

### Start Worker(s)
```bash
python queuectl.py worker start --count 2
```

### Check Job Status
```bash
python queuectl.py status
python queuectl.py list
```

### Manage Dead Letter Queue (DLQ)
```bash
python queuectl.py dlq list
python queuectl.py dlq retry job_fail
```

### Stop Workers
```bash
python queuectl.py worker stop
```

### Manage Config
```bash
python queuectl.py config set backoff_base 2
python queuectl.py config get backoff_base
```

---

## 🧩 Architecture Overview

- **Storage:** SQLite database (`~/.queuectl/queue.db`)  
- **Workers:** Spawned as subprocesses; each executes one job at a time  
- **Retry System:** Exponential backoff (`delay = base ^ attempts`)  
- **DLQ:** Jobs moved to `dead` after exceeding `max_retries`  
- **Persistence:** Job data and config survive restarts  
- **Graceful Shutdown:** Workers finish current jobs before stopping  
- **Cross-Platform:** Fully compatible with Windows and Linux  

---

## 🌟 Bonus Features (Implemented)

| Feature | Description | Status |
|----------|--------------|--------|
| **Job Timeout Handling** | Automatically terminates long-running jobs using `job_timeout` config (default = 30s). | ✅ Implemented |
| **Job Priority Queue** | Higher priority jobs (`priority: 5`) run before lower ones. | ✅ Implemented |
| **Scheduled/Delayed Jobs** | Jobs can be scheduled in advance using a Unix timestamp (`run_at`). | ✅ Implemented |
| **Job Output Logging** | Each job logs output in `~/.queuectl/job_logs/<job_id>.log`. | ✅ Implemented |
| **Metrics Command** | Provides success rate, total jobs, completed and dead counts. | ✅ Implemented |

---

## ⚙️ Extended CLI Examples

### 🔸 Priority Queue Example
```bash
python queuectl.py enqueue "{\"id\":\"urgent_job\",\"command\":\"echo urgent\",\"priority\":5}"
python queuectl.py enqueue "{\"id\":\"normal_job\",\"command\":\"echo normal\",\"priority\":1}"
```
> Result: `urgent_job` runs first because of higher priority.

---

### 🔸 Scheduled / Delayed Jobs
```bash
# Schedule a job to run 30 seconds later
python queuectl.py enqueue "{\"id\":\"future_job\",\"command\":\"echo future\",\"run_at\":$(($(date +%s)+30))}"
```
> The job stays in `pending` until its `run_at` time is reached.

---

### 🔸 Timeout Handling
```bash
# Set a 10-second timeout for all jobs
python queuectl.py config set job_timeout 10
```
> If a job exceeds 10 seconds, it will be terminated and retried with exponential backoff.

---

### 🔸 Job Logs
```bash
# View logs of a specific job
notepad %HOMEPATH%\.queuectl\job_logs\job_ok.log
```
> Each job’s stdout/stderr is saved automatically.

---

### 🔸 System Metrics
```bash
python queuectl.py metrics
```
**Sample Output:**
```
📊 Total jobs: 10
✅ Completed: 8
☠️ Dead: 2
Success rate: 80.0%
```

---

## 🧠 Testing and Automation

### 🔹 Automated Test Script (`tests.py`)
Runs core functional tests automatically:
```bash
python tests.py
```
- Enqueues success and failure jobs  
- Starts worker  
- Waits for retries and DLQ creation  
- Retries DLQ jobs  
- Verifies persistence  

### 🔹 Demo Batch File (`demo.bat`)
Automated CLI demo script:
```bash
demo.bat
```
- Enqueues jobs  
- Starts worker  
- Waits for execution  
- Displays DLQ status  
- Stops worker gracefully  

### 🔹 Design Document (`design.md`)
Summarizes QueueCTL architecture, concurrency model, retry logic, and trade-offs.

---

## 🧪 Test Scenarios

| Test | Expected Outcome |
|------|------------------|
| Successful Job | Moves to `completed` |
| Failed Job | Retries with backoff, then moves to `dead` |
| DLQ Retry | Moves back to `pending` |
| Restart Workers | Pending jobs resume processing |
| Multiple Workers | Parallel, non-overlapping |
| Persistence | Jobs survive restarts |
| Timeout | Job terminated after limit |
| Priority | High-priority jobs executed first |

---

## 📹 Demo Video

**Google Drive Link:** *(paste your uploaded demo link here)*  
Example:  
`https://drive.google.com/file/d/xxxxxxxxxxxxxxxxx/view?usp=sharing`

---

## 🏗️ Deliverables

| File | Description |
|------|--------------|
| `queuectl.py` | Main CLI tool |
| `README.md` | Documentation |
| `demo.bat` | Automated demo |
| `tests.py` | Automated functional test |
| `design.md` | Architecture summary |

---

## 🧠 Developer Notes

- Built using **Python 3.10** and standard libraries + Click  
- Fully persistent, retry-safe, concurrency-protected  
- Includes automation, design, and testing deliverables  
- Verified on Windows environment  
- Extended with timeout, logging, and metrics support  

---

## 💬 Additional Comments

> Implemented QueueCTL in Python with SQLite persistence, exponential backoff retries, multi-worker concurrency, and bonus features including timeout, scheduling, logging, and metrics.  
> Designed and tested for production reliability, clarity, and clean CLI experience.
