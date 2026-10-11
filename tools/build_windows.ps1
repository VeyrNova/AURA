param([string]$Python = ".\.venv\Scripts\python.exe")
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $Python)) { throw "Python runtime not found: $Python" }
& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller is not installed; no packages were installed."; exit 2 }
& $Python -m PyInstaller packaging/windows/aura.spec --noconfirm --clean
