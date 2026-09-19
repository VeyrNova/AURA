@echo off
setlocal
cd /d "%~dp0"
title AURA v0.8.6.1 - CI FULL LANE
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo [1] Smoke lane (rapide)
echo [2] Canonical lane (tous les test_*.py, potentiellement long)
set /p MODE=Choix [1/2] :
if "%MODE%"=="2" (
  "%PY%" -u "%~dp0ci\full_lane.py" --mode canonical
) else (
  "%PY%" -u "%~dp0ci\full_lane.py" --mode smoke
)
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
