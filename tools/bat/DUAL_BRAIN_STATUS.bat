@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" scripts\dual_brain_status.py
) else (
  python scripts\dual_brain_status.py
)
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
