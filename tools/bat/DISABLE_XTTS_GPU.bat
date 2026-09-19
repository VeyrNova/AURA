@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
"venv\Scripts\python.exe" "scripts\disable_xtts_gpu.py"
echo.
pause
