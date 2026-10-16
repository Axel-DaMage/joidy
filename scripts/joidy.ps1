# joidy - CLI for managing the Joidy Docker stack (Windows PowerShell)
#
# Installation:
#   Copy scripts/joidy.ps1 to a folder in your PATH (e.g., $HOME\.local\bin)
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
#   .\joidy.ps1 pull     Pull latest images
#   .\joidy.ps1 logs     Tail logs (all services)
#   .\joidy.ps1 logs api Tail logs for a specific service
#   .\joidy.ps1 idle enable [--idle-hibernate-db]
#                        Start the idle watchdog (auto-sleep when unused)
#   .\joidy.ps1 idle disable   Stop the watchdog (services untouched)
#   .\joidy.ps1 idle status    Watcher state, last activity, time until sleep
#   .\joidy.ps1 help     Show this help message

param(
  [Parameter(Position = 0)]
  [string]$Command = "help",

  [Parameter(Position = 1)]
  [string]$Service = "",

  [Parameter(Position = 2, ValueFromRemainingArguments = $true)]
  [string[]]$Rest = @()
)

function Write-Status($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" -ForegroundColor Blue }
function Write-Ok($msg)     { Write-Host "$([char]0x2713) $msg" -ForegroundColor Green }
function Write-Warn($msg)   { Write-Host "$([char]0x26A0) $msg" -ForegroundColor Yellow }
function Write-Err($msg)    { Write-Host "$([char]0x2717) $msg" -ForegroundColor Red }

# Resolve project directory.
# Priority: JOIDY_DIR env var -> ~/.config/joidy/path file -> script location (../)
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

# --- .env bootstrap -----------------------------------------------
# Resolve which .env file to use:
# 1. $ProjectDir\.env           (git-clone install - writable)
# 2. $env:USERPROFILE\.config\joidy\.env  (AUR/system install - project dir is read-only)
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
    # Project dir is read-only - use user config dir
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
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($bytes)
  return -join ($bytes | ForEach-Object { $_.ToString("x2") })
}

if ($EnvFile -and (Test-Path $EnvFile)) {
  $envContent = Get-Content $EnvFile -Raw
  $changed = $false

  # POSTGRES_PASSWORD
  if ($envContent -match '(?m)^POSTGRES_PASSWORD=(\s*|0+)\s*$') {
    $newPw = Generate-Secret 24
    $envContent = $envContent -replace '(?m)^POSTGRES_PASSWORD=.*', "POSTGRES_PASSWORD=$newPw"
    Write-Ok "Generated POSTGRES_PASSWORD"
    $changed = $true
  }

  # SECRET_KEY
  if ($envContent -match '(?m)^SECRET_KEY=(\s*|change_this_to_a_random_secret_key|0+)\s*$') {
    $newSk = Generate-Secret 32
    $envContent = $envContent -replace '(?m)^SECRET_KEY=.*', "SECRET_KEY=$newSk"
    Write-Ok "Generated SECRET_KEY"
    $changed = $true
  }

  # GRAFANA_ADMIN_PASSWORD
  if ($envContent -match '(?m)^GRAFANA_ADMIN_PASSWORD=(\s*|0+)\s*$') {
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

  # Expand ~ in OBSIDIAN_VAULT_PATH - Docker bind mounts require absolute
  # paths and do not expand `~`. The settings UI lets users enter home-relative
  # paths (e.g. ~/Documentos/notas/mi-vault). Export the expanded value for
  # this compose run; .env keeps the raw ~/... form so the UI stays clean.
  if ($envContent -match '(?m)^OBSIDIAN_VAULT_PATH=(.+)$') {
    $vaultRaw = $Matches[1].Trim()
    $vaultExpanded = $vaultRaw
    if ($vaultRaw -eq '~') {
      $vaultExpanded = $HOME
    } elseif ($vaultRaw -match '^~/(.*)') {
      $vaultExpanded = Join-Path $HOME $Matches[1]
    }
    $vaultExpanded = $vaultExpanded -replace '\\', '/'
    if ($vaultExpanded -ne $vaultRaw) {
      Write-Ok "Expanded OBSIDIAN_VAULT_PATH: $vaultRaw -> $vaultExpanded"
    }
    $env:OBSIDIAN_VAULT_PATH = $vaultExpanded
  }
}

$HIBERNATE_SERVICES = @("ai-service", "worker")

# Idle-watchdog state directory — mirrors the bash CLI: <project>/data/idle,
# falling back to a per-user dir when the project dir is read-only.
$DataDir = Join-Path $ProjectDir "data"
try {
  New-Item -ItemType Directory -Path $DataDir -Force -ErrorAction Stop | Out-Null
} catch {
  $DataDir = Join-Path $env:LOCALAPPDATA "joidy\data"
}
$IdleDir = Join-Path $DataDir "idle"

function Test-Command($Cmd) {
  $null = Get-Command $Cmd -ErrorAction SilentlyContinue
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
  Write-Err "Neither Docker nor Podman is installed or in PATH"
  exit 1
}

function Test-ContainerEngineReady {
  if ($script:containerComposeCmd -like "docker*") {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
      Write-Err "Docker daemon is not responding or Docker Desktop is not running."
      Write-Host "Please start Docker Desktop and verify that the Docker engine is running." -ForegroundColor Yellow
      return $false
    }
  } elseif ($script:containerComposeCmd -like "podman*") {
    $null = podman info 2>&1
    if ($LASTEXITCODE -ne 0) {
      Write-Err "Podman service is not responding or not running."
      return $false
    }
  }
  return $true
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
  Write-Host "+----------------------------------------------+" -ForegroundColor Green
  Write-Host "|  Joidy is running at:                        |" -ForegroundColor Green
  Write-Host "|  http://${ip}:${port}                         |" -ForegroundColor Green
  Write-Host "+----------------------------------------------+" -ForegroundColor Green
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
  if (-not (Test-ContainerEngineReady)) { exit 1 }
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
  if (-not (Test-ContainerEngineReady)) { exit 1 }
  Write-Status "Stopping all Joidy services..."
  Invoke-ComposeCommand @EnvFileArg down
  Write-Ok "All services stopped."
}

function Invoke-Sleep {
  if (-not (Test-ContainerEngineReady)) { exit 1 }
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
  if (-not (Test-ContainerEngineReady)) { exit 1 }
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
  # If the idle watchdog slept the stack, restore the other recorded
  # services too (frontend, postgres, ...).
  $preSleep = Join-Path $IdleDir "pre_sleep_services"
  if (Test-Path $preSleep) {
    Restore-IdleState
    Write-Ok "Restored services recorded before idle sleep."
  }
  if (Test-Path $IdleDir) {
    [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() | Set-Content (Join-Path $IdleDir "last_activity") -ErrorAction SilentlyContinue
  }
  Write-Ok "Wake complete."
}

# --- Idle watchdog (auto-sleep) -------------------------------------
# Mirrors `joidy idle` in scripts/joidy.sh: a background watcher polls
# established TCP connections on the published ports, active PostgreSQL
# sessions, and vault file changes. After JOIDY_IDLE_TIMEOUT minutes (.env,
# default 15) with no activity it snapshots the running services, sleeps the
# stack via the existing sleep path plus the frontend, and keeps postgres
# running unless enabled with --idle-hibernate-db.

function Get-IdleEnv($Name, $Default) {
  if (Get-Item "env:$Name" -ErrorAction SilentlyContinue) {
    $v = (Get-Item "env:$Name").Value
    if ($v) { return $v }
  }
  if ($EnvFile -and (Test-Path $EnvFile)) {
    foreach ($line in (Get-Content $EnvFile -ErrorAction SilentlyContinue)) {
      if ($line -match "^$Name=(.*)$") {
        $v = $Matches[1].Trim()
        if ($v) { return $v }
      }
    }
  }
  return $Default
}

function Write-IdleLog($msg) {
  $log = Join-Path $IdleDir "watcher.log"
  "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg" | Add-Content $log -ErrorAction SilentlyContinue
}

function Get-IdleRunningServices {
  $profile = Get-AiProfileArgs
  $out = Invoke-ComposeCommand @EnvFileArg @profile ps --services --filter status=running 2>$null
  return @($out | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
}

function Test-IdleWatcherAlive {
  $pidFile = Join-Path $IdleDir "watcher.pid"
  if (-not (Test-Path $pidFile)) { return $false }
  $watcherPid = (Get-Content $pidFile -Raw -ErrorAction SilentlyContinue)
  if (-not $watcherPid) { return $false }
  return [bool](Get-Process -Id ([int]$watcherPid.Trim()) -ErrorAction SilentlyContinue)
}

# Signal 1: an established TCP connection on a published service port.
function Test-IdleTcp {
  $ports = @(
    [int](Get-IdleEnv 'FRONTEND_PORT' '3000'),
    [int](Get-IdleEnv 'API_PORT' '8000'),
    [int](Get-IdleEnv 'AI_SERVICE_PORT' '8002'),
    [int](Get-IdleEnv 'WORKER_PORT' '8001')
  )
  foreach ($p in $ports) {
    if (Get-NetTCPConnection -LocalPort $p -State Established -ErrorAction SilentlyContinue) { return $true }
  }
  return $false
}

# Signal 2: an active client session on postgres.
function Test-IdleDb {
  if (-not ((Get-IdleRunningServices) -contains 'postgres')) { return $false }
  $u = Get-IdleEnv 'POSTGRES_USER' 'joidy'
  $d = Get-IdleEnv 'POSTGRES_DB' 'joidy'
  $n = Invoke-ComposeCommand @EnvFileArg exec -T postgres psql -U $u -d $d -tAc `
    "SELECT count(*) FROM pg_stat_activity WHERE state='active' AND pid<>pg_backend_pid()" 2>$null
  $n = ("$n").Trim()
  return ($n -match '^\d+$' -and [int]$n -gt 0)
}

# Signal 3: a vault file changed since the previous poll (marker file mtime).
function Test-IdleVault {
  $vault = $env:OBSIDIAN_VAULT_PATH
  if (-not $vault) { $vault = Join-Path $DataDir 'vault' }
  if (-not (Test-Path $vault)) { return $false }
  $marker = Join-Path $IdleDir 'vault.marker'
  $m = Get-Item $marker -ErrorAction SilentlyContinue
  if (-not $m) { New-Item -ItemType File -Path $marker -Force | Out-Null; return $false }
  $hit = Get-ChildItem -Path $vault -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTimeUtc -gt $m.LastWriteTimeUtc } | Select-Object -First 1
  (Get-Item $marker).LastWriteTimeUtc = [DateTime]::UtcNow
  return [bool]$hit
}

function Test-IdleActivity {
  if (Test-IdleTcp)   { return $true }
  if (Test-IdleDb)    { return $true }
  if (Test-IdleVault) { return $true }
  return $false
}

function Invoke-IdleSleep($HibernateDb) {
  $running = Get-IdleRunningServices
  if ($running.Count -eq 0) {
    Write-IdleLog "idle timeout reached but no services running"
    [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() | Set-Content (Join-Path $IdleDir "last_activity")
    return
  }
  $running | Set-Content (Join-Path $IdleDir "pre_sleep_services")
  Write-IdleLog "idle timeout — sleeping (was running: $($running -join ' '), hibernate_db=$HibernateDb)"
  Invoke-Sleep
  $profile = Get-AiProfileArgs
  if ($running -contains 'frontend') {
    Invoke-ComposeCommand @EnvFileArg @profile stop frontend 2>$null | Out-Null
    Write-IdleLog "stopped frontend"
  }
  if ($HibernateDb -and ($running -contains 'postgres')) {
    Invoke-ComposeCommand @EnvFileArg @profile stop postgres 2>$null | Out-Null
    Write-IdleLog "stopped postgres (--idle-hibernate-db)"
  }
  [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() | Set-Content (Join-Path $IdleDir "slept")
}

function Restore-IdleState {
  $file = Join-Path $IdleDir "pre_sleep_services"
  if (-not (Test-Path $file)) { return }
  $profile = Get-AiProfileArgs
  $running = Get-IdleRunningServices
  $recorded = Get-Content $file | ForEach-Object { $_.Trim() } | Where-Object { $_ }
  foreach ($svc in @('postgres','api','frontend','worker','ai-service') + ($recorded | Where-Object { $_ -notin @('postgres','api','frontend','worker','ai-service') })) {
    if (($recorded -contains $svc) -and (-not ($running -contains $svc))) {
      Invoke-ComposeCommand @EnvFileArg @profile start $svc 2>$null | Out-Null
      Write-IdleLog "restored $svc"
    }
  }
  Remove-Item $file -Force -ErrorAction SilentlyContinue
  Remove-Item (Join-Path $IdleDir "slept") -Force -ErrorAction SilentlyContinue
  [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() | Set-Content (Join-Path $IdleDir "last_activity")
}

# Foreground watcher loop; spawned hidden by `idle enable`.
function Invoke-IdleRun {
  New-Item -ItemType Directory -Path $IdleDir -Force | Out-Null
  $PID | Set-Content (Join-Path $IdleDir "watcher.pid")
  $timeoutMin = [int](Get-IdleEnv 'JOIDY_IDLE_TIMEOUT' '15')
  $pollS = [int](Get-IdleEnv 'JOIDY_IDLE_POLL_SECONDS' '60')
  $hibernate = $false
  $conf = Join-Path $IdleDir "watcher.conf"
  if ((Test-Path $conf) -and (Select-String -Path $conf -Pattern 'IDLE_HIBERNATE_DB=1' -Quiet)) { $hibernate = $true }
  $lastFile = Join-Path $IdleDir "last_activity"
  $sleptFile = Join-Path $IdleDir "slept"
  if (-not (Test-Path $lastFile)) { [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() | Set-Content $lastFile }
  Write-IdleLog "watcher started (pid $PID, timeout=${timeoutMin}m, poll=${pollS}s, hibernate_db=$hibernate)"
  while ($true) {
    try {
      if (Test-IdleActivity) {
        [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() | Set-Content $lastFile
        if (Test-Path $sleptFile) {
          Write-IdleLog "activity detected while asleep — restoring services"
          Restore-IdleState
        }
      } elseif (-not (Test-Path $sleptFile)) {
        $elapsed = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - [int64](Get-Content $lastFile -Raw).Trim()
        if ($elapsed -ge ($timeoutMin * 60)) { Invoke-IdleSleep $hibernate }
      }
    } catch {
      Write-IdleLog "poll error: $_"
    }
    Start-Sleep -Seconds $pollS
  }
}

function Invoke-IdleEnable {
  $hibernate = $Rest -contains '--idle-hibernate-db'
  New-Item -ItemType Directory -Path $IdleDir -Force | Out-Null
  if (Test-IdleWatcherAlive) {
    Write-Warn "Idle watcher already running (pid $((Get-Content (Join-Path $IdleDir 'watcher.pid') -Raw).Trim()))"
    return
  }
  "IDLE_HIBERNATE_DB=$(if ($hibernate) {1} else {0})" | Set-Content (Join-Path $IdleDir "watcher.conf")
  if (-not (Test-Path (Join-Path $IdleDir 'last_activity'))) {
    [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() | Set-Content (Join-Path $IdleDir 'last_activity')
  }
  $exe = (Get-Process -Id $PID).Path
  $proc = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru `
    -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"`"$PSCommandPath`"",'idle','run')
  $proc.Id | Set-Content (Join-Path $IdleDir "watcher.pid")
  Write-Ok "Idle watcher started (pid $($proc.Id))"
  Write-Host "  Sleeps the stack after $(Get-IdleEnv 'JOIDY_IDLE_TIMEOUT' '15') min without activity"
  Write-Host "  (joidy sleep + frontend$(if ($hibernate) {', postgres'})). State: $IdleDir"
}

function Invoke-IdleDisable {
  $pidFile = Join-Path $IdleDir "watcher.pid"
  if (-not (Test-IdleWatcherAlive)) {
    Write-Warn "Idle watcher is not running"
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    return
  }
  $watcherPid = [int]((Get-Content $pidFile -Raw).Trim())
  Stop-Process -Id $watcherPid -Force -ErrorAction SilentlyContinue
  Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
  Write-Ok "Idle watcher stopped (the stack was left untouched)."
}

function Invoke-IdleStatus {
  $timeoutMin = Get-IdleEnv 'JOIDY_IDLE_TIMEOUT' '15'
  $pollS = Get-IdleEnv 'JOIDY_IDLE_POLL_SECONDS' '60'
  Write-Host ""
  if (Test-IdleWatcherAlive) {
    $watcherPid = (Get-Content (Join-Path $IdleDir 'watcher.pid') -Raw).Trim()
    Write-Ok "Idle watcher: RUNNING (pid $watcherPid, poll ${pollS}s)"
  } else {
    Write-Warn "Idle watcher: stopped - enable with 'joidy idle enable'"
  }
  Write-Host "  Timeout:       $timeoutMin min (JOIDY_IDLE_TIMEOUT)"
  $conf = Join-Path $IdleDir "watcher.conf"
  if ((Test-Path $conf) -and (Select-String -Path $conf -Pattern 'IDLE_HIBERNATE_DB=1' -Quiet)) {
    Write-Host "  Hibernate DB:  yes (--idle-hibernate-db)"
  }
  $lastFile = Join-Path $IdleDir "last_activity"
  if (Test-Path $lastFile) {
    $last = [int64](Get-Content $lastFile -Raw).Trim()
    $lastDt = [DateTimeOffset]::FromUnixTimeSeconds($last).LocalDateTime
    Write-Host "  Last activity: $($lastDt.ToString('yyyy-MM-dd HH:mm:ss'))"
    $sleptFile = Join-Path $IdleDir "slept"
    if (Test-Path $sleptFile) {
      $sleptDt = [DateTimeOffset]::FromUnixTimeSeconds([int64](Get-Content $sleptFile -Raw).Trim()).LocalDateTime
      Write-Host "  Stack state:   ASLEEP since $($sleptDt.ToString('yyyy-MM-dd HH:mm:ss'))"
      Write-Host "                 ('joidy wake' restores the recorded services)"
    } else {
      $remaining = [Math]::Max(0, ($timeoutMin * 60) - ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - $last))
      Write-Host "  Sleep in:      ${remaining}s if no new activity"
    }
  } else {
    Write-Host "  Last activity: (not recorded yet)"
  }
  Write-Host ""
}

function Invoke-Idle {
  switch ($Service) {
    'enable'  { Invoke-IdleEnable }
    'disable' { Invoke-IdleDisable }
    'status'  { Invoke-IdleStatus }
    'run'     { Invoke-IdleRun }
    default   {
      Write-Err "Unknown idle subcommand: $Service"
      Write-Host "  Usage: joidy idle enable [--idle-hibernate-db] | disable | status"
      exit 1
    }
  }
}

function Invoke-Restart {
  if (-not (Test-ContainerEngineReady)) { exit 1 }
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
  if (-not (Test-ContainerEngineReady)) { exit 1 }
  Write-Status "Joidy service status:"
  Write-Host ""
  Invoke-ComposeCommand @EnvFileArg ps
}

function Invoke-Pull {
  if (-not (Test-ContainerEngineReady)) { exit 1 }
  Write-Status "Pulling latest Joidy images..."
  $profile = Get-AiProfileArgs
  if ($profile.Count -gt 0) {
    Invoke-ComposeCommand @EnvFileArg @profile pull
  } else {
    Invoke-ComposeCommand @EnvFileArg pull
  }
  Write-Ok "Pull complete."
}

function Invoke-Logs {
  if (-not (Test-ContainerEngineReady)) { exit 1 }
  if ($Service) {
    Invoke-ComposeCommand @EnvFileArg logs -f $Service
  } else {
    Invoke-ComposeCommand @EnvFileArg logs -f
  }
}

function Show-Help {
  Write-Host "joidy - Manage the Joidy Docker stack"
  Write-Host ""
  Write-Host "Usage:"
  Write-Host "  joidy up         Start all services (detached)"
  Write-Host "  joidy down       Stop all services"
  Write-Host "  joidy sleep      Stop heavy services (ai-service, worker) - hibernation"
  Write-Host "  joidy wake       Restart heavy services from hibernation"
  Write-Host "  joidy restart    Restart all services"
  Write-Host "  joidy status     Show service status"
  Write-Host "  joidy pull       Pull latest images"
  Write-Host "  joidy logs       Tail logs (all services)"
  Write-Host "  joidy logs api   Tail logs for a specific service"
  Write-Host "  joidy idle enable [--idle-hibernate-db]"
  Write-Host "                   Start the background idle watchdog (auto-sleep)"
  Write-Host "  joidy idle disable"
  Write-Host "                   Stop the watchdog (running services untouched)"
  Write-Host "  joidy idle status"
  Write-Host "                   Watcher state, last activity, time until sleep"
  Write-Host "  joidy help       Show this help message"
  Write-Host ""
  Write-Host "Idle watchdog: 'joidy idle enable' starts a background watcher that polls"
  Write-Host "established HTTP connections on the published ports, active PostgreSQL"
  Write-Host "sessions, and vault file changes. After JOIDY_IDLE_TIMEOUT minutes (.env,"
  Write-Host "default 15) with no activity it sleeps the stack via 'joidy sleep' plus"
  Write-Host "the frontend; postgres keeps running unless --idle-hibernate-db is given."
  Write-Host "'joidy wake' - or any new activity - restores the recorded services."
  Write-Host ""
  Write-Host "On first run, .env is auto-created from .env.example with generated"
  Write-Host "POSTGRES_PASSWORD, SECRET_KEY, and GRAFANA_ADMIN_PASSWORD."
  Write-Host "For system installs (read-only project dir), .env is stored in"
  Write-Host "~/.config/joidy/.env. Edit it to add GEMINI_API_KEY, OBSIDIAN_VAULT_PATH, etc."
  Write-Host ""
  Write-Host "The project directory is auto-detected from the script location."
}

switch ($Command) {
  "up"            { Invoke-Up }
  "down"          { Invoke-Down }
  "sleep"         { Invoke-Sleep }
  "wake"          { Invoke-Wake }
  "restart"       { Invoke-Restart }
  "status"        { Invoke-Status }
  "pull"          { Invoke-Pull }
  "logs"          { Invoke-Logs }
  "idle"          { Invoke-Idle }
  "help"          { Show-Help }
  "--help"        { Show-Help }
  "-h"            { Show-Help }
  default         { Write-Err "Unknown command: $Command"; Write-Host ""; Show-Help; exit 1 }
}
