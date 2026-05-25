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

    $pluginPath = Join-Path $HermesHome "plugins\memsu\__init__.py"
    $skillPath = Join-Path $HermesHome "skills\memory-capture\SKILL.md"

    Write-Output "Hermes home: $HermesHome"
    Write-Output "Provider installed: $(Test-Path -LiteralPath $pluginPath)"
    Write-Output "Skills installed: $(Test-Path -LiteralPath $skillPath)"
}
finally {
    Pop-Location
}

