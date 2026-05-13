param(
    [string]$TaskName = "CFO Monthly One Pager",
    [string]$RunAt = "08:00",
    [string]$Company = "Your Company"
)

$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$runner = "$projectRoot\scripts\run_monthly_report.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Company `"$Company`""
$trigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1 -At $RunAt
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force
Write-Output "Registered task '$TaskName' to run monthly on day 1 at $RunAt."
