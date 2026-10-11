param(
    [Parameter(Mandatory=$true)]
    [string]$AuditRoot
)

$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -lt 5) {
    Write-Host '[ERROR] Windows PowerShell 5.1 or newer is required.'
    exit 92
}

function Write-Section {
    param([string]$Text)
    Write-Host ''
    Write-Host ('=' * 68)
    Write-Host $Text
    Write-Host ('=' * 68)
}

function Get-AuraNativeProcess {
    param([string]$RootPath)

    $escapedRoot = [Regex]::Escape($RootPath)

    $candidates = Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and
        $_.CommandLine -match 'app[\\/]+main\.py' -and
        (
            $_.CommandLine -match $escapedRoot -or
            $_.ExecutablePath -match 'python'
        )
    }

    if (-not $candidates) {
        return $null
    }

    $best = $candidates |
        Sort-Object CreationDate -Descending |
        Select-Object -First 1

    if (-not $best) {
        return $null
    }

    try {
        return Get-Process -Id ([int]$best.ProcessId) -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Wait-ForAuraNative {
    param([string]$RootPath)

    $proc = Get-AuraNativeProcess -RootPath $RootPath
    if ($proc) {
        return $proc
    }

    Write-Host ''
    Write-Host '[INFO] Native AURA process not detected.'
    Write-Host '[INFO] Trying to launch RUN_NATIVE_UI.bat...'

    $runner = Join-Path $RootPath 'RUN_NATIVE_UI.bat'
    if (-not (Test-Path -LiteralPath $runner)) {
        Write-Host '[ERROR] RUN_NATIVE_UI.bat not found.'
        Write-Host ("        {0}" -f $RootPath)
        return $null
    }

    Start-Process -FilePath $runner -WorkingDirectory $RootPath | Out-Null

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        $proc = Get-AuraNativeProcess -RootPath $RootPath
        if ($proc) {
            Start-Sleep -Seconds 4
            try {
                return Get-Process -Id $proc.Id -ErrorAction Stop
            }
            catch {
                return $null
            }
        }
    }

    return $null
}

function Measure-Phase {
    param(
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][int]$ProcessId,
        [int]$Seconds = 20
    )

    $logical = [Environment]::ProcessorCount
    if ($logical -lt 1) {
        $logical = 1
    }

    $samples = New-Object System.Collections.Generic.List[object]

    $prev = Get-Process -Id $ProcessId -ErrorAction Stop
    $prevCpu = [double]$prev.CPU
    $prevTime = Get-Date

    for ($i = 1; $i -le $Seconds; $i++) {
        Start-Sleep -Seconds 1

        $now = Get-Date
        $proc = Get-Process -Id $ProcessId -ErrorAction Stop

        $cpuNow = [double]$proc.CPU
        $elapsed = ($now - $prevTime).TotalSeconds
        if ($elapsed -le 0) {
            $elapsed = 1.0
        }

        $deltaCpu = [Math]::Max(0.0, $cpuNow - $prevCpu)
        $singleCore = ($deltaCpu / $elapsed) * 100.0
        $normalized = $singleCore / $logical

        $rss = [double]$proc.WorkingSet64 / 1MB
        $private = [double]$proc.PrivateMemorySize64 / 1MB

        $row = New-Object PSObject -Property @{
            Phase = $Name
            Sample = $i
            Timestamp = $now.ToString('HH:mm:ss')
            CpuNormalizedPct = [Math]::Round($normalized, 3)
            CpuSingleCorePct = [Math]::Round($singleCore, 3)
            WorkingSetMB = [Math]::Round($rss, 2)
            PrivateMB = [Math]::Round($private, 2)
        }

        $samples.Add($row)

        Write-Host (
            "[{0,2}/{1}] CPU {2,6:N2}% | RSS {3,7:N1} MB | Private {4,7:N1} MB" -f
            $i, $Seconds, $normalized, $rss, $private
        )

        $prevCpu = $cpuNow
        $prevTime = $now
    }

    return $samples
}

function Get-Summary {
    param(
        [Parameter(Mandatory=$true)]$Samples,
        [Parameter(Mandatory=$true)][string]$Phase
    )

    $cpu = @($Samples | ForEach-Object { $_.CpuNormalizedPct })
    $rss = @($Samples | ForEach-Object { $_.WorkingSetMB })
    $priv = @($Samples | ForEach-Object { $_.PrivateMB })

    return New-Object PSObject -Property @{
        Phase = $Phase
        Samples = $Samples.Count
        CpuAvgPct = [Math]::Round(($cpu | Measure-Object -Average).Average, 3)
        CpuMaxPct = [Math]::Round(($cpu | Measure-Object -Maximum).Maximum, 3)
        RssAvgMB = [Math]::Round(($rss | Measure-Object -Average).Average, 2)
        RssMaxMB = [Math]::Round(($rss | Measure-Object -Maximum).Maximum, 2)
        PrivateAvgMB = [Math]::Round(($priv | Measure-Object -Average).Average, 2)
        PrivateMaxMB = [Math]::Round(($priv | Measure-Object -Maximum).Maximum, 2)
    }
}

function Get-SummaryByName {
    param(
        [Parameter(Mandatory=$true)]$Summaries,
        [Parameter(Mandatory=$true)][string]$Name
    )

    return $Summaries |
        Where-Object { $_.Phase -eq $Name } |
        Select-Object -First 1
}

$proc = Wait-ForAuraNative -RootPath $AuditRoot
if (-not $proc) {
    Write-Host ''
    Write-Host '[ERROR] Could not find or launch the AURA native process.'
    exit 20
}

$processId = [int]$proc.Id
$stamp = (Get-Date).ToString('yyyyMMdd_HHmmss')

$downloads = Join-Path ([Environment]::GetFolderPath('UserProfile')) 'Downloads'
if (-not (Test-Path -LiteralPath $downloads)) {
    $downloads = $AuditRoot
}

$txtPath = Join-Path $downloads ("AURA_POC5_NATIVE_PERF_AUDIT_R2_{0}_RESULT.txt" -f $stamp)
$csvPath = Join-Path $downloads ("AURA_POC5_NATIVE_PERF_AUDIT_R2_{0}_SAMPLES.csv" -f $stamp)

Write-Section -Text 'AURA NATIVE PROCESS'
Write-Host ("PID           : {0}" -f $processId)
Write-Host ("Executable    : {0}" -f $proc.Path)
Write-Host ("Logical CPUs  : {0}" -f [Environment]::ProcessorCount)
Write-Host ("Audit root    : {0}" -f $AuditRoot)

$phaseSpecs = @(
    New-Object PSObject -Property @{
        Name='DARK_COLLAPSED'
        Instruction='Set DARK mode and move the mouse completely OUTSIDE the dock.'
    },
    New-Object PSObject -Property @{
        Name='DARK_EXPANDED'
        Instruction='Stay in DARK mode and keep the mouse INSIDE the dock so it remains expanded.'
    },
    New-Object PSObject -Property @{
        Name='LIGHT_COLLAPSED'
        Instruction='Switch to LIGHT mode and move the mouse completely OUTSIDE the dock.'
    },
    New-Object PSObject -Property @{
        Name='LIGHT_EXPANDED'
        Instruction='Stay in LIGHT mode and keep the mouse INSIDE the dock so it remains expanded.'
    }
)

$allSamples = New-Object System.Collections.Generic.List[object]
$summaries = New-Object System.Collections.Generic.List[object]

foreach ($spec in $phaseSpecs) {
    Write-Section -Text $spec.Name
    Write-Host $spec.Instruction
    Write-Host ''
    Read-Host 'Press ENTER when the UI is ready' | Out-Null

    Write-Host ''
    Write-Host '[INFO] 3-second settle...'
    Start-Sleep -Seconds 3

    try {
        $phaseSamples = Measure-Phase -Name $spec.Name -ProcessId $processId -Seconds 20
    }
    catch {
        Write-Host ''
        Write-Host '[ERROR] Native process disappeared during measurement.'
        Write-Host $_.Exception.Message
        exit 21
    }

    foreach ($sample in $phaseSamples) {
        $allSamples.Add($sample)
    }

    $summary = Get-Summary -Samples $phaseSamples -Phase $spec.Name
    $summaries.Add($summary)
}

$allSamples |
    Select-Object Phase,Sample,Timestamp,CpuNormalizedPct,CpuSingleCorePct,WorkingSetMB,PrivateMB |
    Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8

$machine = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$gpus = @(
    Get-CimInstance Win32_VideoController |
    Select-Object -ExpandProperty Name
)

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add('================================================================')
$lines.Add('AURA POC5 FIX2 - NATIVE PERFORMANCE AUDIT R2')
$lines.Add('READ ONLY')
$lines.Add('================================================================')
$lines.Add('')
$lines.Add(("Date          : {0}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')))
$lines.Add(("Computer      : {0}" -f $env:COMPUTERNAME))
$lines.Add(("Windows       : {0}" -f $os.Caption))
$lines.Add(("Logical CPUs  : {0}" -f [Environment]::ProcessorCount))
$lines.Add(("Installed RAM : {0:N2} GB" -f ([double]$machine.TotalPhysicalMemory / 1GB)))
$lines.Add(("GPU(s)        : {0}" -f ($gpus -join ' / ')))
$lines.Add(("AURA PID      : {0}" -f $processId))
$lines.Add(("Audit root    : {0}" -f $AuditRoot))
$lines.Add('')
$lines.Add('CPU NOTE')
$lines.Add('--------')
$lines.Add('CpuAvgPct/CpuMaxPct are normalized against all logical CPUs.')
$lines.Add('')
$lines.Add('SUMMARY')
$lines.Add('-------')

foreach ($summary in $summaries) {
    $lines.Add((
        "{0,-18} CPU avg {1,6:N3}% | CPU max {2,6:N3}% | RSS avg {3,8:N2} MB | Private avg {4,8:N2} MB" -f
        $summary.Phase,
        $summary.CpuAvgPct,
        $summary.CpuMaxPct,
        $summary.RssAvgMB,
        $summary.PrivateAvgMB
    ))
}

$lines.Add('')
$lines.Add('DELTAS')
$lines.Add('------')

$dc = Get-SummaryByName -Summaries $summaries -Name 'DARK_COLLAPSED'
$de = Get-SummaryByName -Summaries $summaries -Name 'DARK_EXPANDED'
$lc = Get-SummaryByName -Summaries $summaries -Name 'LIGHT_COLLAPSED'
$le = Get-SummaryByName -Summaries $summaries -Name 'LIGHT_EXPANDED'

if ($dc -and $de) {
    $lines.Add((
        "Dock expand DARK : CPU {0:+0.000;-0.000;0.000} pp | RSS {1:+0.00;-0.00;0.00} MB" -f
        ($de.CpuAvgPct - $dc.CpuAvgPct),
        ($de.RssAvgMB - $dc.RssAvgMB)
    ))
}

if ($lc -and $le) {
    $lines.Add((
        "Dock expand LIGHT: CPU {0:+0.000;-0.000;0.000} pp | RSS {1:+0.00;-0.00;0.00} MB" -f
        ($le.CpuAvgPct - $lc.CpuAvgPct),
        ($le.RssAvgMB - $lc.RssAvgMB)
    ))
}

if ($dc -and $lc) {
    $lines.Add((
        "Theme LIGHT/DARK : CPU {0:+0.000;-0.000;0.000} pp | RSS {1:+0.00;-0.00;0.00} MB" -f
        ($lc.CpuAvgPct - $dc.CpuAvgPct),
        ($lc.RssAvgMB - $dc.RssAvgMB)
    ))
}

$lines.Add('')
$lines.Add('FILES')
$lines.Add('-----')
$lines.Add(("Samples CSV : {0}" -f $csvPath))
$lines.Add(("Result TXT  : {0}" -f $txtPath))
$lines.Add('')
$lines.Add('SAFETY')
$lines.Add('------')
$lines.Add('No AURA file was modified.')
$lines.Add('No registry setting was modified.')
$lines.Add('No process was killed.')
$lines.Add('No benchmark tuning flag was applied.')

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines($txtPath, $lines, $utf8NoBom)

Write-Section -Text 'SUMMARY'
$summaries |
    Select-Object Phase,Samples,CpuAvgPct,CpuMaxPct,RssAvgMB,RssMaxMB,PrivateAvgMB,PrivateMaxMB |
    Format-Table -AutoSize

Write-Host ''
Write-Host ("[OK] Result : {0}" -f $txtPath)
Write-Host ("[OK] Samples: {0}" -f $csvPath)
Write-Host ''
exit 0
