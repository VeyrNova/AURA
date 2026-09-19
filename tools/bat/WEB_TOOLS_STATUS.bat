@echo off
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
echo ======================================================
echo AURA v0.7.0 - WEB TOOLS STATUS
echo ======================================================
if not exist "venv\Scripts\python.exe" (
  echo [FAIL] Python venv introuvable.
  pause
  exit /b 1
)
"venv\Scripts\python.exe" "scripts\web_tools_status.py"
set RC=%ERRORLEVEL%
echo.
echo Exit code: %RC%
pause
exit /b %RC%
