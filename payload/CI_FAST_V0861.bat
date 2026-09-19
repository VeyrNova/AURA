@echo off
setlocal
cd /d "%~dp0"
title AURA v0.8.6.1 - CI FAST LANE
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -u "%~dp0ci\fast_lane.py"
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
