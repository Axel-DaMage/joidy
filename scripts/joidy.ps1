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

# Resolve project directory.
# Priority: JOIDY_DIR env var → ~/.config/joidy/path file → script location (../)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($env:JOIDY_DIR -and (Test-Path $env:JOIDY_DIR)) {
  $ProjectDir = $env:JOIDY_DIR
} elseif (Test-Path "$env:USERPROFILE\.config\joidy\path") {
  $ProjectDir = Get-Content "$env:USERPROFILE\.config\joidy\path" -Raw
  $ProjectDir = $ProjectDir.Trim()
} else {
  $ProjectDir = Split-Path -Parent $ScriptDir
}

if (-not (Test-Path "$ProjectDir\docker-compose.yml")) {
  Write-Err "docker-compose.yml not found in $ProjectDir"
  Write-Host "Set JOIDY_DIR env var or create ~/.config/joidy/path with the project path."
  exit 1
}

Set-Location $ProjectDir

$HIBERNATE_SERVICES = @("ai-service", "worker")

function Test-Command($Command) {
  $null = Get-Command $Command -ErrorAction SilentlyContinue
  return $?
}

$script:containerComposeCmd = "docker compose"

if (Test-Command "docker") {
  if (Test-Command "docker-compose") {
    $script:containerComposeCmd = "docker-compose"
  } else {
    $script:containerComposeCmd = "docker compose"
  }
} elseif (Test-Command "podman") {
  if (Test-Command "podman-compose") {
    $script:containerComposeCmd = "podman-compose"
  } else {
    $script:containerComposeCmd = "podman compose"
  }
} else {
  Write-Host "✗ Neither Docker nor Podman is installed or in PATH" -ForegroundColor Red
  exit 1
}

function Invoke-ComposeCommand {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
  )
  if ($script:containerComposeCmd -eq "docker compose") {
    docker compose @ArgsList
  } elseif ($script:containerComposeCmd -eq "docker-compose") {
    docker-compose @ArgsList
  } elseif ($script:containerComposeCmd -eq "podman compose") {
    podman compose @ArgsList
  } elseif ($script:containerComposeCmd -eq "podman-compose") {
    podman-compose @ArgsList
  }
}

function Write-Status($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" -ForegroundColor Blue }
function Write-Ok($msg)     { Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Warn($msg)   { Write-Host "⚠ $msg" -ForegroundColor Yellow }
function Write-Err($msg)    { Write-Host "✗ $msg" -ForegroundColor Red }

function Get-LanIp {
  # Try to get the first non-loopback IPv4 address
  $ip = "localhost"
  try {
    $ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
      Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.PrefixOrigin -ne 'WellKnown' -and $_.IPAddress -notlike '169.254.*' -and $_.IPAddress -notlike '172.*' } |
      Select-Object -First 1
    if ($ips) { $ip = $ips.IPAddress }
  } catch {
    # Fallback for older PowerShell / non-Windows
    $hostEntry = [System.Net.Dns]::GetHostEntry([System.Net.Dns]::GetHostName())
    foreach ($addr in $hostEntry.AddressList) {
      if ($addr.AddressFamily -eq 'InterNetwork' -and $addr.ToString() -ne '127.0.0.1' -and $addr.ToString() -notlike '169.254.*') {
        $ip = $addr.ToString()
        break
      }
    }
  }
  return $ip
}

function Write-AccessUrl {
  $port = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "3000" }
  $ip = Get-LanIp
  Write-Host ""
  Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
  Write-Host "║  Joidy is running at:                        ║" -ForegroundColor Green
  Write-Host "║  http://${ip}:${port}" -ForegroundColor Green
  Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
}

function Invoke-Up {
  Write-Status "Starting Joidy services..."
  Invoke-ComposeCommand up -d
  Write-Status "Waiting for services to stabilize..."
  Start-Sleep -Seconds 5
  Invoke-Status
  Write-AccessUrl
}

function Invoke-Down {
  Write-Status "Stopping all Joidy services..."
  Invoke-ComposeCommand down
  Write-Ok "All services stopped."
}

function Invoke-Sleep {
  Write-Status "Hibernating heavy services (ai-service, worker)..."
  foreach ($svc in $HIBERNATE_SERVICES) {
    $running = Invoke-ComposeCommand ps $svc 2>$null
    if ($running -match $svc) {
      Invoke-ComposeCommand stop $svc
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
    $all = Invoke-ComposeCommand ps -a $svc 2>$null
    if ($all -match $svc) {
      $running = Invoke-ComposeCommand ps $svc 2>$null
      if ($running -match $svc) {
        Write-Warn "$svc is already running"
      } else {
        Invoke-ComposeCommand start $svc
        Write-Ok "Started $svc"
      }
    } else {
      Write-Warn "$svc container not found"
    }
  }
  Write-Host ""
  Write-Ok "Wake complete."
}

function Invoke-Restart {
  Write-Status "Restarting all Joidy services..."
  Invoke-ComposeCommand restart
  Write-Ok "All services restarted."
  Write-AccessUrl
}

function Invoke-Status {
  Write-Status "Joidy service status:"
  Write-Host ""
  Invoke-ComposeCommand ps
}

function Invoke-Logs {
  if ($Service) {
    Invoke-ComposeCommand logs -f $Service
  } else {
    Invoke-ComposeCommand logs -f
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
