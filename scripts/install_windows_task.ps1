[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$TaskName = "memSu Service",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$startScript = Join-Path $RepoRoot "scripts\start_service.ps1"
if (-not (Test-Path -LiteralPath $startScript)) {
    throw "start_service.ps1 not found at $startScript"
}

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$startScript`"",
    "-RepoRoot", "`"$RepoRoot`"",
    "-HostAddress", "`"$HostAddress`"",
    "-Port", [string]$Port
) -join " "

if ($PSCmdlet.ShouldProcess($TaskName, "install memSu Windows Scheduled Task")) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal `
        -UserId $identity `
        -LogonType Interactive `
        -RunLevel LeastPrivilege

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Force | Out-Null

    Write-Output "Installed Windows Scheduled Task '$TaskName' for $identity"
}
Write-Output "Task action: powershell.exe $arguments"
