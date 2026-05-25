[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$TaskName = "memSu Observe",
    [string]$DailyAt = "09:00"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$packageRoot = Join-Path $RepoRoot "memsu"
if (-not (Test-Path -LiteralPath $packageRoot)) {
    throw "memSu package not found under $RepoRoot"
}

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = "-m memsu observe run"
$triggerTime = [datetime]::Today.Add([TimeSpan]::Parse($DailyAt))

if ($PSCmdlet.ShouldProcess($TaskName, "install memSu observe Scheduled Task")) {
    $action = New-ScheduledTaskAction -Execute "python" -Argument $arguments -WorkingDirectory $RepoRoot
    $trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal `
        -UserId $identity `
        -LogonType Interactive `
        -RunLevel Limited

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null

    Write-Output "Installed Windows Scheduled Task '$TaskName' for $identity"
}
Write-Output "Task action: python $arguments"
Write-Output "Working directory: $RepoRoot"
Write-Output "Daily schedule: $DailyAt"
