@echo off
setlocal
cd /d "%~dp0"
if not defined PPE_DEVICE set "PPE_DEVICE=auto"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 65536
) else (
  py -3.11 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 --ws-max-size 65536
)
if errorlevel 1 (
  echo Backend stopped with an error. See README.md for installation and port configuration.
  pause
)
endlocal
