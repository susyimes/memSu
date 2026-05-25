[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$HermesHome = $env:HERMES_HOME
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $HermesHome) {
    $HermesHome = Join-Path $HOME ".hermes"
}

$skillsSource = Join-Path $RepoRoot "hermes\skills"
$skillsDest = Join-Path $HermesHome "skills"

if (-not (Test-Path -LiteralPath $skillsSource)) {
    throw "Missing memSu Hermes skills source: $skillsSource"
}

if ($PSCmdlet.ShouldProcess($HermesHome, "install memSu Hermes skills and initialize CLI store")) {
    New-Item -ItemType Directory -Force -Path $skillsDest | Out-Null
    Copy-Item -Path (Join-Path $skillsSource "*") -Destination $skillsDest -Recurse -Force

    Push-Location $RepoRoot
    try {
        $env:PYTHONPATH = $RepoRoot
        python -m memsu init
        if ($LASTEXITCODE -ne 0) {
            throw "memSu init failed"
        }
        python -m memsu status
        if ($LASTEXITCODE -ne 0) {
            throw "memSu status failed"
        }
    }
    finally {
        Pop-Location
    }

    Write-Output "Installed memSu skills: $skillsDest"
    Write-Output "memSu is CLI-first; no Hermes memory.provider config or resident service was installed."
}
