@echo off
echo =============================
echo  QUEUECTL DEMO STARTING
echo =============================
echo.

REM 1. Check initial status
python queuectl.py status
echo.

REM 2. Enqueue a successful job
python queuectl.py enqueue "{\"id\":\"job_success\",\"command\":\"echo Job completed successfully\",\"max_retries\":2}"
echo.

REM 3. Enqueue a failing job
python queuectl.py enqueue "{\"id\":\"job_fail\",\"command\":\"nonexistent_command\",\"max_retries\":2}"
echo.

REM 4. Start one worker
python queuectl.py worker start --count 1
echo.

REM Wait few seconds
echo Waiting 5 seconds for processing...
timeout /t 5 >nul
echo.

REM 5. Show job status and DLQ
python queuectl.py status
python queuectl.py list
python queuectl.py dlq list
echo.

REM 6. Stop workers
python queuectl.py worker stop
echo.

echo =============================
echo  DEMO COMPLETED SUCCESSFULLY
echo =============================
pause
