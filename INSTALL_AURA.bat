@echo off
setlocal EnableExtensions EnableDelayedExpansion
title AURA - Windows Installer
cd /d "%~dp0"

set "EXPECTED_PYTHON=3.14.7"
set "CORE_LOCK=requirements\locks\windows-py314-core-exact.lock.txt"
set "VOICE_LOCK=requirements\locks\windows-py314-voice-exact.lock.txt"
set "GPU_LOCK=requirements\locks\windows-py314-gpu-exact.lock.txt"
set "DOCS_REQ=requirements\documents.optional.in"
set "GPU_INDEX=https://download.pytorch.org/whl/cu130"
set "PYPI_INDEX=https://pypi.org/simple"

echo ============================================================
echo AURA - REPRODUCIBLE WINDOWS INSTALLER
echo ============================================================
echo.
echo This installer creates a project-local virtual environment.
echo It never writes API keys or OAuth credentials.
echo Ollama is optional and is not installed automatically.
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [FAIL] Python Launcher ^(py.exe^) was not found.
  echo Install CPython %EXPECTED_PYTHON% x64, then run this installer again.
  pause
  exit /b 20
)

for /f "delims=" %%V in ('py -3.14 -c "import platform; print(platform.python_version())" 2^>nul') do set "PYVER=%%V"
if not defined PYVER (
  echo [FAIL] CPython 3.14 x64 is not available through the Windows Python Launcher.
  echo Install CPython %EXPECTED_PYTHON% x64.
  pause
  exit /b 21
)

echo [INFO] Python detected: !PYVER!
if /I not "!PYVER!"=="%EXPECTED_PYTHON%" (
  echo [FAIL] The current certified AURA dependency locks target Python %EXPECTED_PYTHON%.
  echo Detected: !PYVER!
  echo Install the certified Python version before continuing.
  pause
  exit /b 22
)

if not exist "%CORE_LOCK%" (
  echo [FAIL] Missing core dependency lock: %CORE_LOCK%
  pause
  exit /b 23
)
if not exist "%VOICE_LOCK%" (
  echo [FAIL] Missing voice dependency lock: %VOICE_LOCK%
  pause
  exit /b 24
)
if not exist "%GPU_LOCK%" (
  echo [FAIL] Missing GPU dependency lock: %GPU_LOCK%
  pause
  exit /b 25
)

echo.
echo Choose AI mode:
echo   [1] Cloud providers only
echo   [2] Local AI with Ollama
echo   [3] Hybrid local + cloud
choice /C 123 /N /M "Selection [1-3]: "
set "AI_MODE=%ERRORLEVEL%"

if "%AI_MODE%"=="2" goto :check_ollama
if "%AI_MODE%"=="3" goto :check_ollama
goto :after_ollama

:check_ollama
where ollama >nul 2>nul
if errorlevel 1 (
  echo.
  echo [FAIL] Ollama was selected but ollama.exe is not available on PATH.
  echo Install Ollama for Windows separately, then rerun this installer.
  pause
  exit /b 26
)
for /f "delims=" %%O in ('ollama --version 2^>nul') do set "OLLAMA_VERSION=%%O"
echo [PASS] Ollama detected: !OLLAMA_VERSION!

:after_ollama
echo.
echo Choose AURA dependency profile:
echo   [1] Core only
echo   [2] Core + local voice
echo   [3] Core + local voice + NVIDIA CUDA layer
choice /C 123 /N /M "Selection [1-3]: "
set "PROFILE=%ERRORLEVEL%"

if exist "venv\Scripts\python.exe" (
  echo.
  echo Existing venv detected.
  choice /C YN /N /M "Recreate it for a clean install? [Y/N]: "
  if errorlevel 2 goto :use_existing
  echo [INFO] Removing existing venv...
  rmdir /s /q "venv"
)

echo [INFO] Creating clean virtual environment...
py -3.14 -m venv venv
if errorlevel 1 goto :fail

:use_existing
set "PY=venv\Scripts\python.exe"
if not exist "%PY%" goto :fail

echo [INFO] Upgrading pip...
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail

if "%PROFILE%"=="1" goto :install_core
if "%PROFILE%"=="2" goto :install_voice
if "%PROFILE%"=="3" goto :install_gpu
goto :fail

:install_core
echo [INFO] Installing exact CORE lock...
"%PY%" -m pip install --disable-pip-version-check --no-cache-dir -r "%CORE_LOCK%"
if errorlevel 1 goto :fail
goto :optional_docs

:install_voice
echo [INFO] Installing exact VOICE lock...
"%PY%" -m pip install --disable-pip-version-check --no-cache-dir -r "%VOICE_LOCK%"
if errorlevel 1 goto :fail
goto :optional_docs

:install_gpu
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  echo [FAIL] NVIDIA GPU profile selected but nvidia-smi was not found.
  echo Select profile 1 or 2 for a non-CUDA installation.
  goto :fail
)
echo [INFO] Installing exact VOICE base...
"%PY%" -m pip install --disable-pip-version-check --no-cache-dir -r "%VOICE_LOCK%"
if errorlevel 1 goto :fail
echo [INFO] Installing certified CUDA layer from official PyTorch index...
"%PY%" -m pip install --disable-pip-version-check --no-cache-dir ^
  --index-url "%GPU_INDEX%" ^
  --extra-index-url "%PYPI_INDEX%" ^
  -c "%VOICE_LOCK%" ^
  -r "%GPU_LOCK%"
if errorlevel 1 goto :fail
goto :optional_docs

:optional_docs
echo.
choice /C YN /N /M "Install optional document readers (Word/PDF/Excel)? [Y/N]: "
if errorlevel 2 goto :config
if exist "%DOCS_REQ%" (
  echo [INFO] Installing optional document readers...
  "%PY%" -m pip install -r "%DOCS_REQ%"
  if errorlevel 1 goto :fail
)

:config
if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo [INFO] Created local .env from .env.example.
  )
)

echo.
echo [INFO] Running pip dependency check...
"%PY%" -m pip check
if errorlevel 1 goto :fail

echo [INFO] Validating repository dependency closure...
"%PY%" "ci\repository_integrity_gate.py"
if errorlevel 1 (
  echo [FAIL] Source repository is incomplete. AURA will not be marked installable.
  goto :fail
)

echo [INFO] Validating dependency metadata...
"%PY%" "environment\verify_environment.py" --portable
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo PASS - AURA DEPENDENCIES INSTALLED
echo ============================================================
echo.
if "%AI_MODE%"=="1" echo AI mode: Cloud
if "%AI_MODE%"=="2" echo AI mode: Local / Ollama
if "%AI_MODE%"=="3" echo AI mode: Hybrid
if "%PROFILE%"=="1" echo Dependency profile: Core
if "%PROFILE%"=="2" echo Dependency profile: Core + Voice
if "%PROFILE%"=="3" echo Dependency profile: Core + Voice + CUDA
echo.
echo Next:
echo   1. Edit .env with your own provider settings if needed.
echo   2. Run RUN_AURA.bat
echo.
pause
exit /b 0

:fail
echo.
echo ============================================================
echo FAIL - AURA INSTALLATION NOT VALIDATED
echo ============================================================
echo Review the error above. No successful installation is claimed.
echo.
pause
exit /b 1
