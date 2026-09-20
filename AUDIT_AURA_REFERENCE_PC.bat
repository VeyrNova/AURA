@echo off
setlocal EnableExtensions
title AURA - Reference PC Audit
cd /d "%~dp0"

set "PY=venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [FAIL] AURA virtual environment not found: %CD%\venv
  echo Run this audit from the functional AURA source tree.
  pause
  exit /b 20
)

echo ============================================================
echo AURA - REFERENCE PC AUDIT
echo ============================================================
echo.
echo This audit does NOT export:
echo   - API keys or environment values
echo   - OAuth tokens
echo   - conversations or memories
echo   - private voice samples
echo   - user profile paths
echo.
"%PY%" tools\audit_reference_machine.py
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo [PASS] Send back:
  echo ci\reports\reference_machine_audit.json
) else (
  echo [FAIL] Audit failed with code %RC%.
)
echo.
pause
exit /b %RC%
