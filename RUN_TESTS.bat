@echo off
setlocal
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    set "PYEXE=venv\Scripts\python.exe"
) else (
    set "PYEXE=python"
)
for /f "usebackq delims=" %%V in (`"%PYEXE%" -c "from config.settings import settings; print(settings.APP_VERSION)" 2^>nul`) do set "AURA_TEST_VERSION=%%V"
if not defined AURA_TEST_VERSION set "AURA_TEST_VERSION=unknown"
echo ======================================================
echo AURA v%AURA_TEST_VERSION% - Automated test suite
echo ======================================================
"%PYEXE%" -m unittest discover -s tests -v
set TEST_EXIT=%ERRORLEVEL%
echo.
echo Exit code: %TEST_EXIT%
pause
exit /b %TEST_EXIT%
