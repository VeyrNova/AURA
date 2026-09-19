@echo off
setlocal
cd /d "%~dp0"
python tools\diagnose_install.py
pause
