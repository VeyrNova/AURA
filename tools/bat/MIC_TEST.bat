@echo off
setlocal
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" scripts\mic_test.py
) else (
  python scripts\mic_test.py
)
echo.
pause
