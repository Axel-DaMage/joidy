# Joidy installer for Windows (PowerShell)
# Mirrors scripts/install.sh - see that file for behavior notes (#983).
#
# Usage (interactive PowerShell) - the URL is pinned to a release tag so the
# script itself is an immutable artifact (#1394). Check the releases page for
# the latest tag; SHA256SUMS.txt is attached to every release for verifying
# the script before running it:
#   irm https://raw.githubusercontent.com/Axel-DaMage/joidy/v1.1.0-beta.8/scripts/install.ps1 | iex
#
# What it does:
#   1. Checks git and Docker Desktop. If Docker is missing or not running it
#      prints the official download link, waits for one user confirmation and
#      retries once. Docker is never installed automatically.
#   2. Resolves the latest published GitHub release tag via the releases API
#      and clones Axel-DaMage/joidy at that tag (immutable snapshot, #1394)
#      into $env:JOIDY_DIR (default %USERPROFILE%\joidy). An existing checkout
#      is offered an update path; a non-repo directory is never overwritten.
#   3. Bootstraps .env and auto-generates SECRET_KEY + POSTGRES_PASSWORD.
#   4. Asks for GEMINI_API_KEY and the Obsidian vault path (native folder
#      picker when available, text prompt otherwise) and writes them to .env.
#   5. Installs the `joidy` CLI (joidy.ps1 + joidy.cmd shim) into ~/.local/bin.
#   6. Runs `joidy up` when Docker is ready in an interactive session, then
#      opens http://localhost:<FRONTEND_PORT> in the default browser.
#
# Environment overrides:
#   JOIDY_DIR            - install location (default: $HOME\joidy)
#   JOIDY_BRANCH         - dev-only override: git ref to clone instead of the
#                          latest release tag (e.g. development). Do NOT use
#                          for normal installs - branches are mutable (#1394).
#   JOIDY_NONINTERACTIVE - set to 1 to disable all prompts (CI/scripted use)
#   JOIDY_SKIP_START     - set to 1 to skip `joidy up` at the end
$ErrorActionPreference = "Stop"
# Native commands (git, docker) failing must never abort the installer - the
# script inspects $LASTEXITCODE itself instead of throwing on non-zero exits.
if ($PSVersionTable.PSVersion.Major -ge 7) {
  $PSNativeCommandUseErrorActionPreference = $false
}

$Repo = "https://github.com/Axel-DaMage/joidy.git"
$RepoApi = "https://api.github.com/repos/Axel-DaMage/joidy"
# Empty = resolve the latest release tag below (#1394). JOIDY_BRANCH is a
# dev-only override for installing unreleased code.
$Branch = $env:JOIDY_BRANCH
$Dir = if ($env:JOIDY_DIR) { $env:JOIDY_DIR } else { Join-Path $HOME "joidy" }
$NonInteractive = $env:JOIDY_NONINTERACTIVE -eq "1"
$SkipStart = $env:JOIDY_SKIP_START -eq "1"

# Interactive = a real user at a console. CI runners, services and piped
# executions are non-interactive: prompts are skipped, no GUI dialog is shown
# (ShowDialog would block forever in a session with no desktop) and the stack
# is never auto-started unattended - the first `joidy up` pulls GBs of images.
$Interactive = (-not $NonInteractive) -and [Environment]::UserInteractive -and ($env:CI -ne 'true')

function Write-Ok($msg)   { Write-Host "$([char]0x2713) $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "$([char]0x26A0) $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "$([char]0x2717) $msg" -ForegroundColor Red }
function Write-Step($msg) { Write-Host "-> $msg" -ForegroundColor Blue }

# Read-Host throws in non-interactive sessions (CI, `iex` without a console);
# return $null so callers can fall back to instructions instead of aborting.
function Read-UserInput($Prompt) {
  if (-not $Interactive) { return $null }
  try { return Read-Host $Prompt } catch { return $null }
}

# Get-LatestReleaseTag - tag_name of the newest published GitHub release
# (pre-releases included - Joidy ships betas; drafts are never returned by
# the unauthenticated API). $null on network/API failure so callers can
# fall back.
function Get-LatestReleaseTag {
  try {
    $rel = Invoke-RestMethod -Uri "$RepoApi/releases?per_page=1" `
      -Headers @{ "User-Agent" = "joidy-installer" } -TimeoutSec 15
    # @() guards the single-element case: PowerShell unwraps one-item JSON
    # arrays into the bare object, which has no [0] indexer.
    $tag = @($rel)[0].tag_name
    if ($tag) { return $tag }
  } catch { }
  return $null
}

# --- Prerequisites ------------------------------------------------------------
Write-Step "Checking prerequisites..."

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Err "git is required but not installed."
  Write-Host "  Install: winget install Git.Git   or   https://git-scm.com/download/win"
  Write-Err "Please install git and re-run the installer."
  exit 1
}
Write-Ok "git: $((git --version) -replace 'git version ','')"

# Docker must be installed AND the daemon running before the stack can start.
function Test-DockerReady {
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
  $null = docker info 2>$null
  return ($LASTEXITCODE -eq 0)
}

$EngineReady = Test-DockerReady
if ($EngineReady) {
  Write-Ok "Docker: $((docker --version) -replace 'Docker version ','' -replace ',.*','')"
} else {
  Write-Warn "Docker is not installed or not running. Joidy needs Docker Desktop."
  Write-Host "  Download: https://docs.docker.com/desktop/install/windows-install/"
  $resp = Read-UserInput "Press Enter once Docker Desktop is installed and running (Ctrl+C to abort)"
  if ($null -ne $resp -and (Test-DockerReady)) {
    $EngineReady = $true
    Write-Ok "Docker is ready."
  }
  if (-not $EngineReady) {
    Write-Warn "Docker still unavailable - continuing; run 'joidy up' after installing Docker."
  }
}

# --- Release channel (#1394) ---------------------------------------------------
# The default install target is the newest published release tag - an
# immutable snapshot - never a mutable branch. JOIDY_BRANCH overrides this
# for development/testing only.
if (-not $Branch) {
  $Branch = Get-LatestReleaseTag
  if (-not $Branch) {
    $Branch = "main"
    Write-Warn "Could not resolve the latest release tag (offline or rate-limited) - falling back to branch 'main'."
    Write-Warn "Set `$env:JOIDY_BRANCH=<tag> to pin a specific release."
  }
}

# --- Repository ---------------------------------------------------------------
Write-Step "Setting up repository at $Dir..."

if (Test-Path (Join-Path $Dir ".git")) {
  Write-Warn "Existing Joidy checkout found at $Dir"
  $ans = Read-UserInput "Update it now? [Y/n]"
  if ($null -eq $ans) {
    Write-Host "  To update later: re-run this installer or fetch the latest release tag."
  } elseif ($ans -match '^[nN]') {
    Write-Ok "Keeping existing checkout."
  } else {
    # On a real branch (e.g. a JOIDY_BRANCH dev install) fast-forward; on a
    # detached HEAD (release-tag install) `git pull` cannot move the checkout
    # - fetch the newest release tag and move HEAD instead.
    git -C $Dir symbolic-ref -q HEAD 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
      git -C $Dir pull --ff-only 2>$null
      if ($LASTEXITCODE -eq 0) {
        Write-Ok "Updated to latest $Branch."
      } else {
        Write-Warn "git pull failed - keeping current checkout."
      }
    } else {
      $latest = Get-LatestReleaseTag
      $updated = $false
      if ($latest) {
        git -C $Dir fetch --depth 1 origin "tag" $latest 2>$null
        if ($LASTEXITCODE -eq 0) {
          git -C $Dir checkout -q $latest 2>$null
          $updated = ($LASTEXITCODE -eq 0)
        }
      }
      if ($updated) {
        Write-Ok "Updated to $latest."
      } else {
        Write-Warn "Update failed - keeping current checkout."
        Write-Warn "To update manually: cd $Dir ; git fetch --tags ; git checkout <tag>"
      }
    }
  }
} elseif ((Test-Path $Dir) -and (Get-ChildItem $Dir -Force -ErrorAction SilentlyContinue)) {
  # Never overwrite a directory the installer did not create (#983).
  Write-Err "$Dir exists but is not a Joidy git checkout - refusing to overwrite."
  Write-Host "  Move it aside, or install elsewhere with `$env:JOIDY_DIR set to another path."
  exit 1
} else {
  Write-Host "Downloading Joidy ($Branch) to $Dir..."
  git clone --depth 1 --branch $Branch $Repo $Dir
  if ($LASTEXITCODE -ne 0) {
    Write-Err "git clone failed."
    exit 1
  }
  Write-Ok "Cloned '$Branch' into $Dir"
}

# --- .env bootstrap -------------------------------------------------------------
Write-Step "Configuring environment..."

$EnvPath = Join-Path $Dir ".env"
if (-not (Test-Path $EnvPath)) {
  Copy-Item (Join-Path $Dir ".env.example") $EnvPath
  Write-Ok "Created .env from .env.example"
} else {
  Write-Ok ".env already exists - keeping your existing configuration"
}

function New-HexSecret($NumBytes) {
  $bytes = New-Object byte[] $NumBytes
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($bytes)
  return -join ($bytes | ForEach-Object { $_.ToString("x2") })
}

# Read the value of KEY from raw .env content ($null when the line is absent).
function Get-EnvEntry($Content, $Key) {
  $m = [regex]::Match($Content, "(?m)^" + [regex]::Escape($Key) + "=(.*)$")
  if ($m.Success) { return $m.Groups[1].Value.Trim() }
  return $null
}

# Set or append KEY=value line-by-line (no regex replace - user input may
# contain characters that are meaningful in replacement strings).
function Set-EnvValue($Path, $Key, $Value) {
  $lines = [System.Collections.Generic.List[string]]::new()
  foreach ($line in (Get-Content $Path)) { $lines.Add($line) }
  $re = "^" + [regex]::Escape($Key) + "="
  $found = $false
  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match $re) { $lines[$i] = "$Key=$Value"; $found = $true; break }
  }
  if (-not $found) { $lines.Add("$Key=$Value") }
  [System.IO.File]::WriteAllLines($Path, $lines)
}

$envRaw = Get-Content $EnvPath -Raw

$sk = Get-EnvEntry $envRaw "SECRET_KEY"
if ([string]::IsNullOrEmpty($sk) -or $sk -eq "change_this_to_a_random_secret_key") {
  Set-EnvValue $EnvPath "SECRET_KEY" (New-HexSecret 32)
  Write-Ok "Generated SECRET_KEY"
}

$pg = Get-EnvEntry $envRaw "POSTGRES_PASSWORD"
if ([string]::IsNullOrEmpty($pg)) {
  Set-EnvValue $EnvPath "POSTGRES_PASSWORD" (New-HexSecret 24)
  Write-Ok "Generated POSTGRES_PASSWORD"
}

# --- Interactive initial configuration ---------------------------------------
if ($Interactive) {
  Write-Step "Initial configuration (press Enter to skip - you can edit .env later)"
  Write-Host "  Get a free Gemini API key at: https://aistudio.google.com/"

  $gemini = Read-UserInput "  GEMINI_API_KEY"
  if ($gemini) {
    Set-EnvValue $EnvPath "GEMINI_API_KEY" $gemini
    Write-Ok "GEMINI_API_KEY saved to .env"
  }

  # Prefer the OS-native folder picker (the "form" the issue asks for); fall
  # back to a text prompt on Windows PowerShell builds without WinForms.
  $vault = $null
  $picked = $false
  try {
    Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Select your Obsidian vault folder"
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
      $vault = $dialog.SelectedPath
      $picked = $true
    }
    $dialog.Dispose()
  } catch {
    $picked = $false
  }
  if (-not $picked) {
    $v = Read-UserInput "  Path to your Obsidian vault (e.g. $HOME\Documents\MyVault)"
    if ($v) { $vault = $v }
  }
  if ($vault) {
    if (Test-Path $vault) {
      Write-Ok "Vault found: $vault"
    } else {
      Write-Warn "Directory does not exist yet: $vault (create it before 'joidy up')"
    }
    Set-EnvValue $EnvPath "OBSIDIAN_VAULT_PATH" $vault
    Write-Ok "OBSIDIAN_VAULT_PATH saved to .env"
  }
} else {
  Write-Host "  Non-interactive run - set these in $EnvPath before 'joidy up':"
  Write-Host "    GEMINI_API_KEY        (free at https://aistudio.google.com/)"
  Write-Host "    OBSIDIAN_VAULT_PATH   (absolute path to your Obsidian vault)"
}

# --- Install 'joidy' CLI into ~/.local/bin ------------------------------------
Write-Step "Installing joidy CLI..."

$LocalBin = Join-Path $HOME ".local\bin"
$ConfigDir = Join-Path $HOME ".config\joidy"
$JoidyScript = Join-Path $Dir "scripts\joidy.ps1"

New-Item -ItemType Directory -Force -Path $LocalBin | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

# Persist the project path so the CLI survives renames/moves of the install.
Set-Content -Path (Join-Path $ConfigDir "path") -Value $Dir -NoNewline
Write-Ok "Project path saved to $ConfigDir\path"

# Copy the CLI script (overwrite any previous install).
Copy-Item $JoidyScript (Join-Path $LocalBin "joidy.ps1") -Force
Write-Ok "Installed 'joidy' CLI -> $LocalBin\joidy.ps1"

# Create a joidy.cmd shim so users can type `joidy` without the .ps1 extension
# and ensure it executes via PowerShell with ExecutionPolicy Bypass.
$CmdShim = Join-Path $LocalBin "joidy.cmd"
$CmdContent = "@powershell -NoProfile -ExecutionPolicy Bypass -File `"%~dp0joidy.ps1`" %*"
Set-Content -Path $CmdShim -Value $CmdContent -Encoding ASCII
Write-Ok "Created 'joidy.cmd' shim -> $CmdShim"

# --- Ensure ~/.local/bin is in PATH -------------------------------------------
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -and ($UserPath.Split(";") -contains $LocalBin)) {
  Write-Ok "$LocalBin already in user PATH"
} else {
  $NewPath = if ($UserPath) { "$UserPath;$LocalBin" } else { $LocalBin }
  [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
  Write-Ok "Added $LocalBin to user PATH (restart your shell to apply)"
}

# --- ExecutionPolicy Warning / Guidance ---------------------------------------
$effectivePolicy = Get-ExecutionPolicy
if ($effectivePolicy -in @("Restricted", "Undefined")) {
  Write-Host ""
  Write-Warn "PowerShell script execution is restricted on this system ($effectivePolicy)."
  Write-Host "  To run 'joidy' directly in PowerShell without restrictions, run:" -ForegroundColor Yellow
  Write-Host "    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned" -ForegroundColor Cyan
  Write-Host "  Or use 'joidy.cmd' directly from any terminal." -ForegroundColor Gray
}

# --- Start services -------------------------------------------------------------
# Auto-start only in interactive runs with a ready engine: the first `joidy up`
# pulls several container images, so unattended/CI runs just get instructions.
$Started = $false
if ($SkipStart) {
  Write-Host "JOIDY_SKIP_START=1 - skipping service start."
} elseif ($EngineReady -and $Interactive) {
  Write-Step "Starting Joidy services (first run downloads container images)..."
  & $CmdShim up
  if ($LASTEXITCODE -eq 0) {
    $Started = $true
  } else {
    Write-Warn "'joidy up' did not finish cleanly - check 'joidy logs' and retry: joidy up"
  }
} elseif (-not $EngineReady) {
  Write-Warn "Container engine not ready - skipping service start."
}

$FrontendPort = Get-EnvEntry (Get-Content $EnvPath -Raw) "FRONTEND_PORT"
if ([string]::IsNullOrEmpty($FrontendPort)) { $FrontendPort = "3000" }
$JoidyUrl = "http://localhost:$FrontendPort"

if ($Started) {
  Write-Ok "Joidy is running - opening $JoidyUrl in your browser..."
  try { Start-Process $JoidyUrl } catch { }
}

# --- Done ----------------------------------------------------------------------
Write-Host ""
Write-Host "+----------------------------------------------+" -ForegroundColor Green
Write-Host "|   Joidy installed successfully!              |" -ForegroundColor Green
Write-Host "+----------------------------------------------+" -ForegroundColor Green
Write-Host ""

if ($Started) {
  Write-Host "Joidy is running:  $JoidyUrl" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "  Manage it with the 'joidy' CLI (restart your shell if it is not found):"
} else {
  Write-Host "Next steps:" -ForegroundColor Yellow
  Write-Host ""
  $n = 1
  $envNow = Get-Content $EnvPath -Raw
  if ([string]::IsNullOrEmpty((Get-EnvEntry $envNow "GEMINI_API_KEY"))) {
    Write-Host "  $n. Set your GEMINI_API_KEY (free at https://aistudio.google.com/):"
    Write-Host "       notepad $EnvPath"
    Write-Host ""
    $n++
  }
  $vaultCfg = Get-EnvEntry $envNow "OBSIDIAN_VAULT_PATH"
  if ([string]::IsNullOrEmpty($vaultCfg) -or -not (Test-Path $vaultCfg)) {
    Write-Host "  $n. Set your Obsidian vault path in .env (OBSIDIAN_VAULT_PATH=...)"
    Write-Host ""
    $n++
  }
  if (-not $EngineReady) {
    Write-Host "  $n. Install Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"
    Write-Host ""
    $n++
  }
  Write-Host "  $n. Restart your shell (so 'joidy' is in PATH), then run: joidy up"
}
Write-Host ""
Write-Host "Help:    joidy help" -ForegroundColor Blue
Write-Host "Logs:    joidy logs" -ForegroundColor Blue
Write-Host "Stop:    joidy down" -ForegroundColor Blue
Write-Host "Update:  re-run this installer (it moves the checkout to the newest release tag)" -ForegroundColor Blue
Write-Host ""
