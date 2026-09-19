@echo off
setlocal
cd /d "%~dp0"
python scripts\configure_groq.py
pause
