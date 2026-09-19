@echo off
setlocal EnableExtensions DisableDelayedExpansion
title REFRESH AURA MUSIC UI2
set "ROOT=C:\AURA GPT version"
if exist "%ROOT%\venv\Scripts\python.exe" (
  set "PY=%ROOT%\venv\Scripts\python.exe"
) else (
  set "PY=python.exe"
)
"%PY%" "C:\AURA GPT version\runtime\aura_music_ui_sync_v180.py"
echo(
pause
