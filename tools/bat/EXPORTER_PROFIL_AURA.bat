@echo off
setlocal
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0aura_profile_cli.py" export
echo.
pause
