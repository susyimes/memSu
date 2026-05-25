param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
Push-Location $RepoRoot
try {
    $env:PYTHONPATH = $RepoRoot
    python -m memsu service status
}
finally {
    Pop-Location
}

