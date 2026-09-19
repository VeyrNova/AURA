@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "AURA_ROOT=%~dp0.."
for %%I in ("%AURA_ROOT%") do set "AURA_ROOT=%%~fI"
set "PY=%AURA_ROOT%\venv\Scripts\python.exe"
if not exist "%PY%" (
  endlocal & set "AURA_LOCALE=fr-FR" & set "STT_LANGUAGE=fr" & set "AURA_TTS_LANGUAGE=fr" & set "AURA_RESPONSE_LANGUAGE=French" & exit /b 0
)
"%PY%" "%AURA_ROOT%\localization\select_language.py" --ensure >nul 2>nul
set "LOCALE=fr-FR"
set "AURA_LOCALE_TMP=%TEMP%\aura_locale_current_%RANDOM%%RANDOM%.txt"
"%PY%" "%AURA_ROOT%\localization\aura_locale.py" --get > "%AURA_LOCALE_TMP%" 2>nul
if exist "%AURA_LOCALE_TMP%" (
  set /p LOCALE=<"%AURA_LOCALE_TMP%"
  del /q "%AURA_LOCALE_TMP%" >nul 2>nul
)
if /I "%LOCALE%"=="en-US" (
  set "STT=en"
  set "TTS=en"
  set "RESP=English"
) else (
  set "LOCALE=fr-FR"
  set "STT=fr"
  set "TTS=fr"
  set "RESP=French"
)
set "UIROOT=%LOCALAPPDATA%\AURA\ui\v0.7.2.2-rc4.2"
if exist "%UIROOT%\dist\assets" (
  > "%UIROOT%\dist\assets\aura-selected-locale.js" echo window.__AURA_BOOT_LOCALE__="%LOCALE%";
)
endlocal & set "AURA_LOCALE=%LOCALE%" & set "STT_LANGUAGE=%STT%" & set "AURA_TTS_LANGUAGE=%TTS%" & set "XTTS_LANGUAGE=%TTS%" & set "AURA_RESPONSE_LANGUAGE=%RESP%" & exit /b 0
