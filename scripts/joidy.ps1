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

function Write-Status($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" -ForegroundColor Blue }
function Write-Ok($msg)     { Write-Host "✓ $msg" -ForegroundColor Green }
function Write-Warn($msg)   { Write-Host "⚠ $msg" -ForegroundColor Yellow }
function Write-Err($msg)    { Write-Host "✗ $msg" -ForegroundColor Red }

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

# ─── .env bootstrap ───────────────────────────────────────────────
# Resolve which .env file to use:
# 1. $ProjectDir\.env           (git-clone install — writable)
# 2. $env:USERPROFILE\.config\joidy\.env  (AUR/system install — project dir is read-only)
# 3. Auto-create from .env.example with generated secrets
$ConfigDirJoidy = Join-Path $env:USERPROFILE ".config\joidy"
$EnvFile = ""
$EnvFileArg = @()

if (Test-Path "$ProjectDir\.env") {
  $EnvFile = "$ProjectDir\.env"
} elseif ((Test-Path "$ProjectDir\.env.example") -and -not (Test-Path "$ProjectDir\.env")) {
  # Check if project dir is writable
  $canWrite = $false
  try {
    $testFile = Join-Path $ProjectDir ".joidy_write_test"
    [System.IO.File]::WriteAllText($testFile, "test")
    Remove-Item $testFile -Force
    $canWrite = $true
  } catch {
    $canWrite = $false
  }

  if ($canWrite) {
    Copy-Item "$ProjectDir\.env.example" "$ProjectDir\.env"
    $EnvFile = "$ProjectDir\.env"
    Write-Status "Created .env from .env.example"
  } else {
    # Project dir is read-only — use user config dir
    if (-not (Test-Path $ConfigDirJoidy)) {
      New-Item -ItemType Directory -Path $ConfigDirJoidy -Force | Out-Null
    }
    $EnvFile = Join-Path $ConfigDirJoidy ".env"
    if (-not (Test-Path $EnvFile)) {
      Copy-Item "$ProjectDir\.env.example" $EnvFile
      Write-Status "Created .env in $ConfigDirJoidy (project dir is read-only)"
    }
    $EnvFileArg = @("--env-file", $EnvFile)
  }
}

# Auto-generate required secrets if empty or placeholder
function Generate-Secret($Length) {
  $bytes = New-Object byte[] $Length
  (New-Object Security.Cryptography.RandomNumberGenerator).GetBytes($bytes)
  return -join ($bytes | ForEach-Object { $_.ToString("x2") })
}

if ($EnvFile -and (Test-Path $EnvFile)) {
  $envContent = Get-Content $EnvFile -Raw
  $changed = $false

  # POSTGRES_PASSWORD
  if ($envContent -match '(?m)^POSTGRES_PASSWORD=\s*$') {
    $newPw = Generate-Secret 24
    $envContent = $envContent -replace '(?m)^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$newPw"
    Write-Ok "Generated POSTGRES_PASSWORD"
    $changed = $true
  }

  # SECRET_KEY
  if ($envContent -match '(?m)^SECRET_KEY=(\s*|change_this_to_a_random_secret_key)\s*$') {
    $newSk = Generate-Secret 32
    $envContent = $envContent -replace '(?m)^SECRET_KEY=.*', "SECRET_KEY=$newSk"
    Write-Ok "Generated SECRET_KEY"
    $changed = $true
  }

  # GRAFANA_ADMIN_PASSWORD
  if ($envContent -match '(?m)^GRAFANA_ADMIN_PASSWORD=\s*$') {
    $newGrafanaPw = Generate-Secret 24
    $envContent = $envContent -replace '(?m)^GRAFANA_ADMIN_PASSWORD=.*', "GRAFANA_ADMIN_PASSWORD=$newGrafanaPw"
    Write-Ok "Generated GRAFANA_ADMIN_PASSWORD"
    $changed = $true
  }

  if ($changed) {
    $envContent | Set-Content $EnvFile -NoNewline
    Write-Warn "Auto-generated required secrets in $EnvFile"
    Write-Warn "Edit $EnvFile to add: GEMINI_API_KEY, OBSIDIAN_VAULT_PATH, etc."
  }
}

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

function Get-AiProfileArgs {
  if ($EnvFile -and (Test-Path $EnvFile)) {
    $lines = Get-Content $EnvFile -ErrorAction SilentlyContinue
    foreach ($line in $lines) {
      if ($line -match '^\s*AI_SERVICE_ENABLED\s*=\s*true\s*$') {
        return @("--profile", "ai")
      }
    }
  }
  return @()
}

function Invoke-Up {
  Write-Status "Starting Joidy services..."
  $profile = Get-AiProfileArgs
  if ($profile.Count -gt 0) {
    Invoke-ComposeCommand @EnvFileArg @profile up -d
  } else {
    Invoke-ComposeCommand @EnvFileArg up -d
  }
  Write-Status "Waiting for services to stabilize..."
  Start-Sleep -Seconds 5
  Invoke-Status
  Write-AccessUrl
}

function Invoke-Down {
  Write-Status "Stopping all Joidy services..."
  Invoke-ComposeCommand @EnvFileArg down
  Write-Ok "All services stopped."
}

function Invoke-Sleep {
  Write-Status "Hibernating heavy services (ai-service, worker)..."
  foreach ($svc in $HIBERNATE_SERVICES) {
    $running = Invoke-ComposeCommand @EnvFileArg ps $svc 2>$null
    if ($running -match $svc) {
      Invoke-ComposeCommand @EnvFileArg stop $svc
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
  $profile = Get-AiProfileArgs
  foreach ($svc in $HIBERNATE_SERVICES) {
    $all = Invoke-ComposeCommand @EnvFileArg @profile ps -a $svc 2>$null
    if ($all -match $svc) {
      $running = Invoke-ComposeCommand @EnvFileArg @profile ps $svc 2>$null
      if ($running -match $svc) {
        Write-Warn "$svc is already running"
      } else {
        Invoke-ComposeCommand @EnvFileArg @profile start $svc
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
  $profile = Get-AiProfileArgs
  if ($profile.Count -gt 0) {
    Invoke-ComposeCommand @EnvFileArg @profile restart
  } else {
    Invoke-ComposeCommand @EnvFileArg restart
  }
  Write-Ok "All services restarted."
  Write-AccessUrl
}

function Invoke-Status {
  Write-Status "Joidy service status:"
  Write-Host ""
  Invoke-ComposeCommand @EnvFileArg ps
}

function Invoke-Logs {
  if ($Service) {
    Invoke-ComposeCommand @EnvFileArg logs -f $Service
  } else {
    Invoke-ComposeCommand @EnvFileArg logs -f
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
  Write-Host "On first run, .env is auto-created from .env.example with generated"
  Write-Host "POSTGRES_PASSWORD, SECRET_KEY, and GRAFANA_ADMIN_PASSWORD."
  Write-Host "For system installs (read-only project dir), .env is stored in"
  Write-Host "~/.config/joidy/.env. Edit it to add GEMINI_API_KEY, OBSIDIAN_VAULT_PATH, etc."
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
