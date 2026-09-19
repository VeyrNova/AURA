@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PIDFILE=%LOCALAPPDATA%\AURA\vitals\healthkit_bridge_v185.pid"
if not exist "%PIDFILE%" (
 echo [INFO] H185 bridge is not running.
 pause
 exit /b 0
)
set /p BRIDGEPID=<"%PIDFILE%"
if "%BRIDGEPID%"=="" (
 echo [BLOCKED] PID file is empty.
 pause
 exit /b 2
)
taskkill /PID %BRIDGEPID% /T /F >nul 2>nul
if errorlevel 1 (
 echo [BLOCKED] Could not stop H185 bridge PID %BRIDGEPID%.
 pause
 exit /b 2
)
del /q "%PIDFILE%" >nul 2>nul
echo [PASS] H185 bridge stopped.
pause
