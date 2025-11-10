import subprocess
import time

def run(cmd):
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout.strip(), "\n")

print("=== QueueCTL Automated Test Script ===")

# 1. Check initial status
run("python queuectl.py status")

# 2. Enqueue success and fail jobs
run('python queuectl.py enqueue "{\\"id\\":\\"auto_success\\",\\"command\\":\\"echo auto ok\\",\\"max_retries\\":2}"')
run('python queuectl.py enqueue "{\\"id\\":\\"auto_fail\\",\\"command\\":\\"nonexistent_cmd\\",\\"max_retries\\":2}"')

# 3. Start workers
run("python queuectl.py worker start --count 1")

# 4. Wait to process jobs
print("Waiting for jobs to process...")
time.sleep(6)

# 5. Check status and DLQ
run("python queuectl.py status")
run("python queuectl.py dlq list")

# 6. Retry DLQ job
run("python queuectl.py dlq retry auto_fail")

# 7. Final status
run("python queuectl.py status")

print("=== Automated Tests Completed ===")
