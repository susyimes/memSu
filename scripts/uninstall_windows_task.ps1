[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$TaskName = "memSu Observe"
)

$ErrorActionPreference = "Stop"

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Output "Windows Scheduled Task '$TaskName' is not installed"
    exit 0
}

if ($PSCmdlet.ShouldProcess($TaskName, "remove memSu Windows Scheduled Task")) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "Removed Windows Scheduled Task '$TaskName'"
}
