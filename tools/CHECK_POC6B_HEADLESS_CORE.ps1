param(
    [string]$Root = ""
)

$ErrorActionPreference = 'Stop'

function Find-CoreRoot {
    param([string]$Explicit)

    $candidates = @()

    if ($Explicit) {
        $candidates += $Explicit
    }
    if ($env:AURA_ROOT) {
        $candidates += $env:AURA_ROOT
    }

    $override = Join-Path (Split-Path -Parent $PSScriptRoot) 'AURA_ROOT_OVERRIDE.txt'
    if (Test-Path -LiteralPath $override) {
        try {
            $candidate = (Get-Content -LiteralPath $override -Raw -Encoding UTF8).Trim().Trim('"')
            if ($candidate) {
                $candidates += $candidate
            }
        } catch {}
    }

    $candidates += 'C:\AURA GPT version'
    $candidates += 'C:\AURA'

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not $candidate) { continue }
        $main = Join-Path $candidate 'main.py'
        $python = Join-Path $candidate 'venv\Scripts\python.exe'
        $version = Join-Path $candidate 'VERSION'
        if ((Test-Path $main) -and (Test-Path $python) -and (Test-Path $version)) {
            return $candidate
        }
    }

    return $null
}

$core = Find-CoreRoot -Explicit $Root

Write-Host '================================================================'
Write-Host 'AURA POC6B - HEADLESS CORE DIAGNOSTIC'
Write-Host '================================================================'
Write-Host ''

if (-not $core) {
    Write-Host '[ERROR] AURA Core installation not found.'
    Write-Host '[INFO] Put its root path in AURA_ROOT_OVERRIDE.txt.'
    exit 10
}

Write-Host ('[OK] AURA Core : ' + $core)

$session = Join-Path $env:LOCALAPPDATA 'AURA\ui\runtime\rc4_2_session.json'
if (-not (Test-Path -LiteralPath $session)) {
    Write-Host '[INFO] No active RC4.2 session yet.'
} else {
    try {
        $data = Get-Content -LiteralPath $session -Raw -Encoding UTF8 | ConvertFrom-Json
        $url = 'http://127.0.0.1:' + [int]$data.port + '/api/status?token=' + [Uri]::EscapeDataString([string]$data.token)
        $status = Invoke-RestMethod -UseBasicParsing -Method Get -Uri $url -TimeoutSec 2
        Write-Host ('[OK] Session reachable on port ' + [int]$data.port)
        Write-Host ('     Interaction ready: ' + $status.interaction_ready)
        Write-Host ('     Voice state      : ' + $status.voice_state)
    } catch {
        Write-Host '[INFO] Session file exists but host is not reachable.'
    }
}

$statusPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'runtime\poc6b_headless_core_status.json'
if (Test-Path -LiteralPath $statusPath) {
    try {
        $h = Get-Content -LiteralPath $statusPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-Host ''
        Write-Host '[POC6B HEADLESS HOST]'
        Write-Host ('State      : ' + $h.state)
        Write-Host ('PID        : ' + $h.pid)
        Write-Host ('No browser : ' + $h.no_browser)
        Write-Host ('UI root    : ' + $h.ui_root)
    } catch {}
}

Write-Host ''
Write-Host 'This diagnostic never displays the RC4.2 session token.'
exit 0
