@echo off
setlocal
cd /d "%~dp0"
title AURA v0.8.6.2.2 - STRICT COLD INSTALL VERIFIER

set "PY=%~dp0venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [FAIL] Venv AURA introuvable.
  pause
  exit /b 2
)

echo ============================================================================================================
echo AURA v0.8.6.2.2 - EXACT TRANSITIVE COLD INSTALL
echo ============================================================================================================
echo.
echo [1] Preflight CORE strict, sans reseau
echo [2] Cold install CORE strict reel
echo [3] Cold install VOICE strict reel
echo [4] Preflight GPU/FULL strict, sans reseau
echo [5] Cold install GPU/FULL strict reel - cache autorise
echo [6] Cold install GPU/FULL strict reel - SANS CACHE
echo [7] Cold install FULL strict reel - cache autorise
echo.
set /p MODE=Choix [1/2/3/4/5/6/7] :

if "%MODE%"=="2" (
  "%PY%" -u "%~dp0environment\cold_install_verifier.py" --profile core --network
) else if "%MODE%"=="3" (
  "%PY%" -u "%~dp0environment\cold_install_verifier.py" --profile voice --network
) else if "%MODE%"=="4" (
  "%PY%" -u "%~dp0environment\cold_install_verifier.py" --profile gpu
) else if "%MODE%"=="5" (
  "%PY%" -u "%~dp0environment\cold_install_verifier.py" --profile gpu --network
) else if "%MODE%"=="6" (
  echo.
  echo [INFO] Le mode sans cache peut retelecharger environ 1.9 Go pour torch CUDA.
  echo.
  "%PY%" -u "%~dp0environment\cold_install_verifier.py" --profile gpu --network --no-cache
) else if "%MODE%"=="7" (
  "%PY%" -u "%~dp0environment\cold_install_verifier.py" --profile full --network
) else (
  "%PY%" -u "%~dp0environment\cold_install_verifier.py" --profile core
)
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
