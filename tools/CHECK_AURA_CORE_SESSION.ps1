$ErrorActionPreference = 'Stop'

$session = Join-Path $env:LOCALAPPDATA 'AURA\ui\runtime\rc4_2_session.json'

Write-Host '================================================================'
Write-Host 'AURA POC6 - CORE BRIDGE DIAGNOSTIC'
Write-Host '================================================================'
Write-Host ''

if (-not (Test-Path -LiteralPath $session)) {
    Write-Host '[OFFLINE] RC4.2 session file not found.'
    Write-Host ('          ' + $session)
    exit 10
}

try {
    $data = Get-Content -LiteralPath $session -Raw -Encoding UTF8 | ConvertFrom-Json
    $port = [int]$data.port
    $token = [string]$data.token
    if ($port -lt 1 -or $token.Length -lt 24) {
        throw 'invalid session contract'
    }

    $encoded = [Uri]::EscapeDataString($token)
    $url = 'http://127.0.0.1:' + $port + '/api/status?token=' + $encoded
    $status = Invoke-RestMethod -UseBasicParsing -Method Get -Uri $url -TimeoutSec 3

    Write-Host '[OK] Core session reachable.'
    Write-Host ('PID               : ' + $data.pid)
    Write-Host ('Port              : ' + $port)
    Write-Host ('Release           : ' + $status.release)
    Write-Host ('Interaction ready : ' + $status.interaction_ready)
    Write-Host ('Voice state       : ' + $status.voice_state)
    Write-Host ('Service bridge    : ' + $status.core_service_bridge)
    Write-Host ''
    Write-Host 'Security: the session token is intentionally NOT displayed.'
    exit 0
}
catch {
    Write-Host '[OFFLINE] Session exists but Core is not reachable.'
    Write-Host ('Reason: ' + $_.Exception.Message)
    exit 11
}
