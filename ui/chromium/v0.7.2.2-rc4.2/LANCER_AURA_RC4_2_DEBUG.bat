@echo off
setlocal
cd /d "%~dp0"
python tools\launch_shell.py --debug
pause
