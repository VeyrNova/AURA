@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
set "PYTHONUNBUFFERED=1"
if not exist "logs" mkdir "logs"
echo === AURA XTTS GPU PROBE - EXPERIMENTAL ===
echo.
echo ATTENTION: ne lance ce test QUE si XTTS_CPU_PROBE.bat est PASS.
echo Si le pilote graphique est instable, ce test peut provoquer un reset d'affichage.
echo.
choice /C ON /N /M "Tape O pour continuer ou N pour annuler: "
if errorlevel 2 exit /b 0
if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" -u scripts\xtts_safe_probe.py --device cuda --result temp\xtts_gpu_probe.json 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath 'logs\xtts_gpu_probe.log'"
) else (
  python -u scripts\xtts_safe_probe.py --device cuda --result temp\xtts_gpu_probe.json 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath 'logs\xtts_gpu_probe.log'"
)
echo.
echo Log: logs\xtts_gpu_probe.log
pause
