\# QueueCTL – Backend Developer Assignment (FLAM)



A CLI-based background job queue system built in \*\*Python\*\* that manages background jobs, retries failures with \*\*exponential backoff\*\*, and maintains a \*\*Dead Letter Queue (DLQ)\*\*.



---



\## ⚙️ Tech Stack

\- \*\*Language:\*\* Python 3.10  

\- \*\*Libraries:\*\* Click (CLI), SQLite3 (standard library)  

\- \*\*Tested On:\*\* Windows 10/11  



---



\## 🎯 Objective

Build a minimal production-grade \*\*background job queue system\*\* that supports:

\- Enqueuing and managing background jobs  

\- Running multiple worker processes  

\- Retrying failed jobs automatically with exponential backoff  

\- Maintaining a Dead Letter Queue (DLQ)  

\- Persistent job storage across restarts  

\- All features accessible via CLI  



---



\## ⚙️ Setup Instructions

```bash

cd flam-queuectl

python -m venv venv

venv\\Scripts\\activate

pip install click

python queuectl.py status

```



---



\## 💻 Usage Examples (Windows CMD / PowerShell)



\### Enqueue Jobs

```bash

python queuectl.py enqueue "{\\"id\\":\\"job\_ok\\",\\"command\\":\\"echo hello\\",\\"max\_retries\\":2}"

python queuectl.py enqueue "{\\"id\\":\\"job\_fail\\",\\"command\\":\\"nonexistent\_cmd\\",\\"max\_retries\\":2}"

```



\### Start Worker(s)

```bash

python queuectl.py worker start --count 2

```



\### Check Job Status

```bash

python queuectl.py status

python queuectl.py list

```



\### Manage Dead Letter Queue (DLQ)

```bash

python queuectl.py dlq list

python queuectl.py dlq retry job\_fail

```



\### Stop Workers

```bash

python queuectl.py worker stop

```



\### Manage Config

```bash

python queuectl.py config set backoff\_base 2

python queuectl.py config get backoff\_base

```



---



\## 🧩 Architecture Overview

\- \*\*Storage:\*\* SQLite database (`~/.queuectl/queue.db`)

\- \*\*Workers:\*\* Spawned as subprocesses; each executes one job at a time  

\- \*\*Retry System:\*\* Exponential backoff (`delay = base ^ attempts`)  

\- \*\*DLQ:\*\* Jobs moved to `dead` after exceeding `max\_retries`  

\- \*\*Persistence:\*\* Job data and config survive restarts  

\- \*\*Graceful Shutdown:\*\* Workers finish current jobs before stopping  



---



\## 🧠 Testing and Automation



\### 🔹 Automated Test Script (`tests.py`)

Runs core functional tests automatically:

```bash

python tests.py

```

\- Enqueues success and failure jobs  

\- Starts worker  

\- Waits for retries and DLQ creation  

\- Retries DLQ jobs  

\- Verifies persistence  



\### 🔹 Demo Batch File (`demo.bat`)

Automated CLI demo script:

```bash

demo.bat

```

\- Enqueues jobs  

\- Starts worker  

\- Waits for execution  

\- Displays DLQ status  

\- Stops worker gracefully  



\### 🔹 Design Document (`design.md`)

Summarizes QueueCTL architecture, concurrency model, retry logic, and trade-offs.



---



\## 🧪 Test Scenarios

| Test | Expected Outcome |

|------|------------------|

| Successful Job | Moves to `completed` |

| Failed Job | Retries with backoff, then moves to `dead` |

| DLQ Retry | Moves back to `pending` |

| Restart Workers | Pending jobs resume processing |

| Multiple Workers | Parallel, non-overlapping |

| Persistence | Jobs survive restarts |



---



\## 📹 Demo Video

\*\*Google Drive Link:\*\* \*(paste your uploaded demo link here)\*  

Example:  

`https://drive.google.com/file/d/xxxxxxxxxxxxxxxxx/view?usp=sharing`



---



\## 🏗️ Deliverables

| File | Description |

|------|--------------|

| `queuectl.py` | Main CLI tool |

| `README.md` | Documentation |

| `demo.bat` | Automated demo |

| `tests.py` | Automated functional test |

| `design.md` | Architecture summary |



---



\## 🧠 Developer Notes

\- Built using \*\*Python 3.10\*\* and standard libraries + Click  

\- Fully persistent, retry-safe, and concurrency-protected  

\- Includes automation, design, and testing deliverables  

\- Verified on Windows environment  



---



\## 💬 Additional Comments

> Implemented QueueCTL in Python with SQLite persistence, exponential backoff retries, and multi-worker concurrency.  

> Added automated test script, demo batch file, and design documentation for complete production-grade coverage.



