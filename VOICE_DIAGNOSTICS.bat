@echo off
setlocal
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" scripts\voice_diagnostics.py
) else (
  python scripts\voice_diagnostics.py
)
echo.
pause
