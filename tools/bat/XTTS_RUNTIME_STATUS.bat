@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONPATH=%CD%
if not exist "venv\Scripts\python.exe" (
  echo [FAIL] venv introuvable.
  pause
  exit /b 2
)
"venv\Scripts\python.exe" "scripts\xtts_runtime_status.py"
echo.
pause
