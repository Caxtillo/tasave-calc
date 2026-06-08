# Run this script as Administrator to schedule daily BCV scraping
$scriptPath = Join-Path $PSScriptRoot "scrape_daily.bat"
$taskName = "TasaVes-BCV-Scraper"
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$scriptPath`""

$trigger = New-ScheduledTaskTrigger -Daily -At 5pm
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force

Write-Host "Task '$taskName' created - runs daily at 5:00 PM"
