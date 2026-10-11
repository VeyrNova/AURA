$ErrorActionPreference = 'Stop'

$session = Join-Path $env:LOCALAPPDATA 'AURA\ui\runtime\rc4_2_session.json'

if (-not (Test-Path -LiteralPath $session)) {
    Write-Host '[INFO] No RC4.2 session file found.'
    exit 0
}

try {
    $data = Get-Content -LiteralPath $session -Raw -Encoding UTF8 | ConvertFrom-Json
    $port = [int]$data.port
    $token = [string]$data.token
    $url = 'http://127.0.0.1:' + $port + '/api/shutdown?token=' + [Uri]::EscapeDataString($token)
    $body = [Text.Encoding]::UTF8.GetBytes('{}')
    $request = [Net.HttpWebRequest]::Create($url)
    $request.Method = 'POST'
    $request.ContentType = 'application/json'
    $request.ContentLength = $body.Length
    $stream = $request.GetRequestStream()
    $stream.Write($body,0,$body.Length)
    $stream.Close()
    $response = $request.GetResponse()
    $response.Close()
    Write-Host '[OK] Shutdown request sent to the active AURA Core session.'
    exit 0
}
catch {
    Write-Host ('[WARN] Core shutdown request failed: ' + $_.Exception.Message)
    exit 1
}
