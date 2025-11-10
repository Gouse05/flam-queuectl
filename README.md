\# QueueCTL – Backend Developer Assignment (FLAM)



A CLI-based background job queue system built in \*\*Python\*\* that manages background jobs, retries failures with \*\*exponential backoff\*\*, and maintains a \*\*Dead Letter Queue (DLQ)\*\*.



---



\## ⚙️ Setup Instructions



\### 1. Clone or extract the repository

```bash

cd flam-queuectl

```



\### 2. Create virtual environment and install dependencies

```bash

python -m venv venv

venv\\Scripts\\activate

pip install click

```



\### 3. Check status (DB initializes automatically)

```bash

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

python queuectl.py worker start --count 1

```



\### Check Job Status

```bash

python queuectl.py status

python queuectl.py list

```



\### Dead Letter Queue (DLQ)

```bash

python queuectl.py dlq list

python queuectl.py dlq retry job\_fail

```



\### Stop Workers

```bash

python queuectl.py worker stop

```



\### Config Example

```bash

python queuectl.py config set backoff\_base 2

python queuectl.py config get backoff\_base

```



---



\## 🧩 Architecture Overview

\- \*\*Storage:\*\* SQLite database (`~/.queuectl/queue.db`)

\- \*\*Worker Management:\*\* Workers launched as subprocesses with PID tracking

\- \*\*Retry Mechanism:\*\* Exponential backoff → delay = base ^ attempts

\- \*\*DLQ Handling:\*\* Jobs moved to `dead` after `max\_retries`

\- \*\*Persistence:\*\* Jobs survive restarts

\- \*\*Graceful Shutdown:\*\* Workers finish current job before stopping



---



\## 🧠 Test Scenarios

| Test | Expected Outcome |

|------|------------------|

| Successful Job | Moves to `completed` |

| Failed Job | Retries, then moves to `dead` |

| DLQ Retry | Moves back to `pending` |

| Restart Workers | Pending jobs resume processing |

| Multiple Workers | Parallel, no duplicate execution |



---



\## 📹 Demo Video

\*\*Google Drive Link:\*\* \*(upload your recording and paste link here)\*  

Example:  

`https://drive.google.com/file/d/xxxxxxxxxxxxxxxxx/view?usp=sharing`



---



\## 🏗️ Deliverables

\- `queuectl.py` → main CLI program  

\- `README.md` → this file  

\- (Optional) `demo.sh` → script to auto-run demo



---



\## 🧠 Developer Notes

\- Built with Python 3.10 using only standard libraries + `click`

\- Persistent and concurrent system

\- Tested on Windows 10



