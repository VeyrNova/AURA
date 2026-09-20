@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "AURA_ROOT=%CD%"
set "PYTHONPATH=%AURA_ROOT%;%PYTHONPATH%"
set "BOOTSTRAP=%AURA_ROOT%\tools\aura_v2_product_bootstrap.py"
set "PYW=%AURA_ROOT%\venv\Scripts\pythonw.exe"
set "PY=%AURA_ROOT%\venv\Scripts\python.exe"

if not exist "%BOOTSTRAP%" exit /b 90

if /I "%~1"=="--self-check" goto :self_check

REM AURA_I18N_R1_PREPARE_LOCALE
call "%~dp0localization\prepare_locale.bat"
REM /AURA_I18N_R1_PREPARE_LOCALE

if exist "%PYW%" (
    start "" "%PYW%" "%BOOTSTRAP%"
    exit /b 0
)

if exist "%PY%" (
    start "" /b "%PY%" "%BOOTSTRAP%"
    exit /b 0
)

exit /b 91

:self_check
if not exist "%PY%" exit /b 91
"%PY%" "%BOOTSTRAP%" --self-check
exit /b %ERRORLEVEL%
