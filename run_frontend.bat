@echo off
setlocal
cd /d "%~dp0frontend"
if not exist "node_modules\vite\bin\vite.js" (
  echo Installing frontend dependencies with the pinned npm version...
  call npx --yes npm@11.6.2 ci --no-fund
  if errorlevel 1 exit /b 1
)
call npm run dev
endlocal
