param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$memsuHome = if ($env:MEMSU_HOME) { $env:MEMSU_HOME } else { Join-Path $HOME ".memsu" }
New-Item -ItemType Directory -Force -Path $memsuHome | Out-Null
$pidFile = Join-Path $memsuHome "memsu.pid"
$logFile = Join-Path $memsuHome "memsu.log"
$errFile = Join-Path $memsuHome "memsu.err.log"

if (Test-Path -LiteralPath $pidFile) {
    $existingPid = Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existingPid) {
        $proc = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Output "memSu service already running with PID $existingPid"
            exit 0
        }
    }
}

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$RepoRoot$([System.IO.Path]::PathSeparator)$env:PYTHONPATH"
}
else {
    $env:PYTHONPATH = $RepoRoot
}

$args = @(
    "-m", "memsu", "serve",
    "--host", $HostAddress,
    "--port", [string]$Port
)

$process = Start-Process -FilePath "python" `
    -ArgumentList $args `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $errFile `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $process.Id
Write-Output "Started memSu service on http://$HostAddress`:$Port with PID $($process.Id)"
