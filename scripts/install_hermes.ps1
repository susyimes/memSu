[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$HermesHome = $env:HERMES_HOME,
    [switch]$PatchConfig
)

$ErrorActionPreference = "Stop"

function Set-HermesMemoryConfig {
    param(
        [string]$ConfigPath
    )

    $backupPath = "$ConfigPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    if (Test-Path -LiteralPath $ConfigPath) {
        Copy-Item -LiteralPath $ConfigPath -Destination $backupPath -Force
        $lines = @(Get-Content -LiteralPath $ConfigPath -Encoding UTF8)
    }
    else {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ConfigPath) | Out-Null
        $lines = @()
    }

    $memoryIndex = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^memory:\s*$') {
            $memoryIndex = $i
            break
        }
    }

    if ($memoryIndex -lt 0) {
        $lines += ""
        $lines += "memory:"
        $lines += "  enabled: true"
        $lines += "  provider: memsu"
    }
    else {
        $endIndex = $lines.Count
        for ($i = $memoryIndex + 1; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match '^\S') {
                $endIndex = $i
                break
            }
        }

        $enabledFound = $false
        $providerFound = $false
        for ($i = $memoryIndex + 1; $i -lt $endIndex; $i++) {
            if ($lines[$i] -match '^\s+enabled:') {
                $lines[$i] = "  enabled: true"
                $enabledFound = $true
            }
            elseif ($lines[$i] -match '^\s+provider:') {
                $lines[$i] = "  provider: memsu"
                $providerFound = $true
            }
        }

        $insert = @()
        if (-not $enabledFound) { $insert += "  enabled: true" }
        if (-not $providerFound) { $insert += "  provider: memsu" }
        if ($insert.Count -gt 0) {
            $before = if ($memoryIndex -ge 0) { $lines[0..$memoryIndex] } else { @() }
            $after = if ($memoryIndex + 1 -lt $lines.Count) { $lines[($memoryIndex + 1)..($lines.Count - 1)] } else { @() }
            $lines = @($before + $insert + $after)
        }
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($ConfigPath, [string[]]$lines, $utf8NoBom)
    if (Test-Path -LiteralPath $backupPath) {
        Write-Output "Backed up Hermes config to $backupPath"
    }
}

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
if (-not $HermesHome) {
    $HermesHome = Join-Path $HOME ".hermes"
}

$pluginSource = Join-Path $RepoRoot "hermes\plugins\memory\memsu"
$pluginDest = Join-Path $HermesHome "plugins\memsu"
$skillsSource = Join-Path $RepoRoot "hermes\skills"
$skillsDest = Join-Path $HermesHome "skills"

if (-not (Test-Path -LiteralPath $pluginSource)) {
    throw "Missing memSu Hermes provider source: $pluginSource"
}

if ($PSCmdlet.ShouldProcess($HermesHome, "install memSu Hermes provider and skills")) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $pluginDest) | Out-Null
    New-Item -ItemType Directory -Force -Path $pluginDest | Out-Null
    New-Item -ItemType Directory -Force -Path $skillsDest | Out-Null
    Get-ChildItem -LiteralPath $pluginSource -Force |
        Where-Object { $_.Name -ne "__pycache__" } |
        Copy-Item -Destination $pluginDest -Recurse -Force
    Copy-Item -Path (Join-Path $skillsSource "*") -Destination $skillsDest -Recurse -Force

    Push-Location $RepoRoot
    try {
        $env:PYTHONPATH = $RepoRoot
        python -m memsu init
        if ($LASTEXITCODE -ne 0) {
            throw "memSu init failed"
        }
    }
    finally {
        Pop-Location
    }

    if ($PatchConfig) {
        Set-HermesMemoryConfig -ConfigPath (Join-Path $HermesHome "config.yaml")
    }
    else {
        Write-Output "Config patch skipped. Add this to $HermesHome\config.yaml or rerun with -PatchConfig:"
        Write-Output "memory:"
        Write-Output "  enabled: true"
        Write-Output "  provider: memsu"
    }

    Write-Output "Installed memSu provider: $pluginDest"
    Write-Output "Installed memSu skills: $skillsDest"
}
