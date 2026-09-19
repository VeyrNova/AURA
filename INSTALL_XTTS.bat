@echo off
setlocal
cd /d "%~dp0"
echo === AURA v0.5.2 - XTTS-v2 ===
if not exist venv\Scripts\python.exe (
  echo [INFO] Creation de l'environnement virtuel...
  py -m venv venv
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip uv
if errorlevel 1 goto :fail
REM Recommandation actuelle Coqui: uv choisit automatiquement le backend PyTorch adapte.
uv pip install torch torchaudio torchcodec --torch-backend=auto
if errorlevel 1 goto :fail
uv pip install "coqui-tts>=0.27.4,<0.29"
if errorlevel 1 goto :fail
python scripts\setup_xtts.py
if errorlevel 1 goto :fail
echo.
echo [OK] XTTS-v2 est pret.
pause
exit /b 0
:fail
echo.
echo [FAIL] Installation XTTS interrompue. Consulte le message ci-dessus.
pause
exit /b 1
