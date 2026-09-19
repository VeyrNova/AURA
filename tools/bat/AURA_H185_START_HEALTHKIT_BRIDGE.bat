@echo off
setlocal EnableExtensions DisableDelayedExpansion
title AURA H185 HealthKit Bridge v1.8.5 - LAN Pairing
set "ROOT=C:\AURA GPT version"
if exist "%ROOT%\venv\Scripts\python.exe" (set "PY=%ROOT%\venv\Scripts\python.exe") else (set "PY=python.exe")
echo AURA H185 HealthKit Bridge - private LAN paired mode
echo Port: 18585
echo Pairing details: %LOCALAPPDATA%\AURA\vitals\iphone_pairing_v185.txt
echo(
"%PY%" -u "%ROOT%\runtime\aura_healthkit_bridge_v185.py"
