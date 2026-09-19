@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
if not exist "venv\Scripts\python.exe" (
  echo [FAIL] venv introuvable.
  pause
  exit /b 2
)
"venv\Scripts\python.exe" "scripts\enable_xtts_gpu.py"
echo.
pause
