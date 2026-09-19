@echo off
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"
set "VENDOR=%~dp0vendor\search_rc24"
echo [INFO] Installation / mise a jour du moteur de recherche Web gratuit DDGS...
if exist "%VENDOR%" rmdir /s /q "%VENDOR%"
py -3 -m pip install --disable-pip-version-check --no-input --target "%VENDOR%" "ddgs>=9.14.4,<10"
if errorlevel 1 goto :fail
py -3 -c "import sys; sys.path.insert(0, r'%VENDOR%'); from ddgs import DDGS; import importlib.metadata as m; print('[OK] DDGS', m.version('ddgs'), 'pret.')"
if errorlevel 1 goto :fail
echo [OK] Recherche Web gratuite prete. Redemarre AURA.
pause
exit /b 0
:fail
echo [ERREUR] Impossible d'installer DDGS. Verifie la connexion Internet puis reessaie.
pause
exit /b 1
