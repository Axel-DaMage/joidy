# joidy — CLI for managing the Joidy Docker stack (Windows PowerShell)
#
# Installation:
#   Copy scripts/joidy.ps1 to a folder in your PATH (e.g., $HOME\bin)
#   Or add the scripts folder to your PATH:
#     [Environment]::SetEnvironmentVariable("Path", $env:Path + ";$PWD\scripts", "User")
#
# Usage:
#   .\joidy.ps1 up       Start all services (detached)
#   .\joidy.ps1 down     Stop all services
#   .\joidy.ps1 sleep    Stop heavy services (ai-service, worker)
#   .\joidy.ps1 wake     Restart heavy services from hibernation
#   .\joidy.ps1 restart  Restart all services
#   .\joidy.ps1 status   Show service status
#   .\joidy.ps1 logs     Tail logs (all services)
#   .\joidy.ps1 logs api Tail logs for a specific service
#   .\joidy.ps1 help     Show this help message

param(
  [Parameter(Position = 0)]
  [string]$Command = "help",

  [Parameter(Position = 1)]
  [string]$Service = ""
)

# Resolve project directory from script location
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Set-Location $ProjectDir

$HIBERNATE_SERVICES = @("ai-service", "worker")

function Write-Status($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" -ForegroundColor Blue }
function Write-Ok($msg)     { Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Warn($msg)   { Write-Host "⚠ $msg" -ForegroundColor Yellow }
function Write-Err($msg)    { Write-Host "✗ $msg" -ForegroundColor Red }

function Invoke-Up {
  Write-Status "Starting Joidy services..."
  docker compose up -d
  Write-Status "Waiting for services to stabilize..."
  Start-Sleep -Seconds 5
  Invoke-Status
}

function Invoke-Down {
  Write-Status "Stopping all Joidy services..."
  docker compose down
  Write-Ok "All services stopped."
}

function Invoke-Sleep {
  Write-Status "Hibernating heavy services (ai-service, worker)..."
  foreach ($svc in $HIBERNATE_SERVICES) {
    $running = docker compose ps --status running $svc 2>$null
    if ($running -match $svc) {
      docker compose stop $svc
      Write-Ok "Stopped $svc"
    } else {
      Write-Warn "$svc is already stopped"
    }
  }
  Write-Host ""
  Write-Ok "Hibernation complete. API, frontend, and database are still running."
  Write-Host "  Use 'joidy wake' to restart heavy services."
}

function Invoke-Wake {
  Write-Status "Waking heavy services from hibernation..."
  foreach ($svc in $HIBERNATE_SERVICES) {
    $stopped = docker compose ps --status stopped $svc 2>$null
    if ($stopped -match $svc) {
      docker compose start $svc
      Write-Ok "Started $svc"
    } else {
      Write-Warn "$svc is already running"
    }
  }
  Write-Host ""
  Write-Ok "Wake complete."
}

function Invoke-Restart {
  Write-Status "Restarting all Joidy services..."
  docker compose restart
  Write-Ok "All services restarted."
}

function Invoke-Status {
  Write-Status "Joidy service status:"
  Write-Host ""
  docker compose ps
}

function Invoke-Logs {
  if ($Service) {
    docker compose logs -f $Service
  } else {
    docker compose logs -f
  }
}

function Show-Help {
  Write-Host "joidy — Manage the Joidy Docker stack"
  Write-Host ""
  Write-Host "Usage:"
  Write-Host "  joidy up         Start all services (detached)"
  Write-Host "  joidy down       Stop all services"
  Write-Host "  joidy sleep      Stop heavy services (ai-service, worker) — hibernation"
  Write-Host "  joidy wake       Restart heavy services from hibernation"
  Write-Host "  joidy restart    Restart all services"
  Write-Host "  joidy status     Show service status"
  Write-Host "  joidy logs       Tail logs (all services)"
  Write-Host "  joidy logs api   Tail logs for a specific service"
  Write-Host "  joidy help       Show this help message"
  Write-Host ""
  Write-Host "The project directory is auto-detected from the script location."
}

switch ($Command) {
  "up"      { Invoke-Up }
  "down"    { Invoke-Down }
  "sleep"   { Invoke-Sleep }
  "wake"    { Invoke-Wake }
  "restart" { Invoke-Restart }
  "status"  { Invoke-Status }
  "logs"    { Invoke-Logs }
  "help"    { Show-Help }
  default   { Write-Err "Unknown command: $Command"; Write-Host ""; Show-Help; exit 1 }
}
