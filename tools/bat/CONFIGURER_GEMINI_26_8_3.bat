@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
title AURA - Configuration Gemini 26.8.3
color 0B
cls
echo ============================================================
echo  AURA - CONFIGURATION GEMINI 26.8.3
echo ============================================================
echo.
set "AURA_ROOT=%~1"
if not defined AURA_ROOT set "AURA_ROOT=C:\AURA GPT version"
if not exist "%AURA_ROOT%\main.py" set /p "AURA_ROOT=Chemin du dossier AURA : "
if not exist "%AURA_ROOT%\main.py" (
  echo [ERREUR] Installation AURA introuvable : "%AURA_ROOT%"
  goto :HOLD
)
set "PY_CMD="
where py >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"
if not defined PY_CMD (
  where python >nul 2>&1
  if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
  echo [ERREUR] Python introuvable dans le PATH.
  goto :HOLD
)
if not exist "%AURA_ROOT%\scripts\configure_gemini.py" (
  echo [ERREUR] scripts\configure_gemini.py introuvable.
  echo Lance d'abord APPLIQUER_PATCH_26_8_3.bat
  goto :HOLD
)
pushd "%AURA_ROOT%"
%PY_CMD% scripts\configure_gemini.py
set "RC=%ERRORLEVEL%"
popd
echo.
if "%RC%"=="0" (
  echo [OK] Configuration Gemini terminee.
) else (
  echo [ERREUR] La configuration Gemini a retourne le code %RC%.
)
:HOLD
echo.
echo La fenetre reste ouverte. Appuie sur une touche quand tu as fini de lire.
pause >nul
endlocal
