@echo off
setlocal
set "AURA_ROOT=C:\AURA GPT version"
set "PY=%AURA_ROOT%\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%AURA_ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%AURA_ROOT%\launch_aura_dev_agent.py" grok_build %*
exit /b %ERRORLEVEL%
