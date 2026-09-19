@echo off
setlocal
cd /d "%~dp0"
title AURA v0.8.6.2 - VERIFY ENVIRONMENT
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [FAIL] Venv AURA introuvable.
  pause
  exit /b 2
)
"%PY%" -u "%~dp0environment\verify_environment.py"
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
