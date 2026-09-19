@echo off
setlocal
cd /d "%~dp0"
echo ======================================================
echo AURA - Gradium True Realtime WebSocket

echo Installation de websockets 16.1.1 (BSD, gratuit)...
python -m pip install "websockets==16.1.1"
if errorlevel 1 (
  echo.
  echo ECHEC: impossible d'installer websockets.
  echo AURA continuera avec le fallback REST Gradium.
  pause
  exit /b 1
)
echo.
python -c "import websockets; print('websockets', websockets.__version__, 'OK')"
echo.
echo Installation terminee. Redemarre AURA pour utiliser Gradium WebSocket.
pause
