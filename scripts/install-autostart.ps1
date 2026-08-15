# install-autostart.ps1 — Set up Windows Task Scheduler for Joidy auto-start on logon.
#
# Usage:
#   .\scripts\install-autostart.ps1          # Install auto-start
#   .\scripts\install-autostart.ps1 -Remove  # Remove auto-start

param(
  [switch]$Remove = $false
)

$TaskName = "Joidy"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

if ($Remove) {
  Write-Host "Removing Joidy auto-start task..."
  $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
  if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "✓ Joidy auto-start task removed."
  } else {
    Write-Host "⚠ No Joidy auto-start task found."
  }
  exit 0
}

Write-Host "Setting up Joidy auto-start via Windows Task Scheduler..."

# Check if running on Windows
$osEnv = $env:OS
if ($PSVersionTable.Platform -ne "Win32NT" -and (-not $osEnv -or -not $osEnv.Contains("Windows"))) {
  Write-Host "⚠ This script is for Windows. For Linux, use install-autostart.sh"
  exit 1
}

# Create the scheduled task action
$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -Command `"Set-Location '$ProjectDir'; docker compose up -d`""

# Trigger at user logon
$Trigger = New-ScheduledTaskTrigger -AtLogOn

# Settings: don't start if already running, allow start on battery
$Settings = New-ScheduledTaskSettingsSet `
  -DontStartIfOnBatteries:$false `
  -AllowStartIfOnBatteries `
  -StartWhenAvailable

# Register the task
Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Settings $Settings `
  -Description "Start Joidy Docker services on logon" `
  -Force

Write-Host ""
Write-Host "✓ Joidy auto-start task installed."
Write-Host ""
Write-Host "The services will start automatically when you log in."
Write-Host ""
Write-Host "Manual commands:"
Write-Host "  Start-ScheduledTask -TaskName Joidy    # Start now"
Write-Host "  Stop-ScheduledTask -TaskName Joidy     # Stop now"
Write-Host "  Get-ScheduledTask -TaskName Joidy      # Check status"
Write-Host ""
Write-Host "To remove auto-start: .\scripts\install-autostart.ps1 -Remove"
