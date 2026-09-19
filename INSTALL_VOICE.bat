@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo AURA v0.5.1 - Installation voix locale
echo ============================================

if not exist "venv\Scripts\python.exe" (
    echo [ERREUR] Environnement venv introuvable.
    echo Cree-le d'abord avec: python -m venv venv
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :error

python -m pip install -r requirements-voice-pinned.txt
if errorlevel 1 goto :error

python scripts\setup_voice.py
if errorlevel 1 goto :error

echo.
echo [OK] Installation vocale terminee.
pause
exit /b 0

:error
echo.
echo [ERREUR] L'installation vocale a echoue.
echo Copie la sortie de cette fenetre dans ton rapport de bug.
pause
exit /b 1
