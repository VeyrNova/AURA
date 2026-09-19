@echo off
setlocal
cd /d "%~dp0"
set "PROFILE=%~1"
if "%PROFILE%"=="" (
  set /p "PROFILE=Chemin du fichier .auraprofile : "
)
if "%PROFILE%"=="" exit /b 2
echo.
echo ==================== PREVISUALISATION ====================
"%~dp0venv\Scripts\python.exe" "%~dp0aura_profile_cli.py" preview "%PROFILE%"
if errorlevel 1 goto :end
echo.
set /p "OK=Appliquer cet import avec backup ? [O/N] : "
if /I not "%OK%"=="O" (
  echo [ANNULE] Aucune modification.
  goto :end
)
"%~dp0venv\Scripts\python.exe" "%~dp0aura_profile_cli.py" import "%PROFILE%" --apply
:end
echo.
pause
