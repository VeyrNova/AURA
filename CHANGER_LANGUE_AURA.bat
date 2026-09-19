@echo off
setlocal EnableExtensions
title AURA - Langue / Language
set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [FAIL] Python AURA introuvable.
  pause
  exit /b 20
)
"%PY%" "%~dp0localization\select_language.py" --change
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (
  echo [PASS] Langue enregistree. Redemarre AURA pour appliquer partout.
) else (
  echo [FAIL] Modification de langue impossible.
)
pause
exit /b %RC%
