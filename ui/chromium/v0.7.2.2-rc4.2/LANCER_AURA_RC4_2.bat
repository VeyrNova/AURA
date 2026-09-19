@echo off
setlocal
cd /d "%~dp0"
python tools\launch_shell.py
if errorlevel 1 (
  echo [ERREUR] Le lanceur RC4.2 a echoue. Utilise LANCER_AURA_RC4_2_DEBUG.bat pour le diagnostic.
  pause
)
