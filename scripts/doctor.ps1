param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$HermesHome = $env:HERMES_HOME
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $HermesHome) {
    $HermesHome = Join-Path $HOME ".hermes"
}

Push-Location $RepoRoot
try {
    $env:PYTHONPATH = $RepoRoot
    python -m memsu doctor
    if ($LASTEXITCODE -ne 0) {
        throw "memSu doctor failed"
    }
    python -m memsu status
    if ($LASTEXITCODE -ne 0) {
        throw "memSu status failed"
    }
    python -m memsu observe doctor
    if ($LASTEXITCODE -ne 0) {
        throw "memSu observe doctor failed"
    }
    python -m memsu migrate status
    if ($LASTEXITCODE -ne 0) {
        throw "memSu migration status failed"
    }
    python -m memsu privacy scan --limit 20
    if ($LASTEXITCODE -ne 0) {
        throw "memSu privacy scan failed"
    }

    $skillPath = Join-Path $HermesHome "skills\memory-capture\SKILL.md"

    Write-Output "Hermes home: $HermesHome"
    Write-Output "Skills installed: $(Test-Path -LiteralPath $skillPath)"
}
finally {
    Pop-Location
}
