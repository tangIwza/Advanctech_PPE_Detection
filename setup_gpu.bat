@echo off
setlocal
cd /d "%~dp0"
nvidia-smi -L
if errorlevel 1 (
  echo An NVIDIA GPU and its driver are required. See docs/GPU_SETUP.md.
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install torch==2.2.2+cu121 torchvision==0.17.2+cu121 --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r backend/requirements.txt -c backend/constraints-gpu.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -c "import torch; assert torch.cuda.is_available(), 'CUDA is not available'; print('GPU ready:', torch.cuda.get_device_name(0))"
if errorlevel 1 exit /b 1
echo GPU setup complete. Start the application with run_backend.bat.
endlocal
