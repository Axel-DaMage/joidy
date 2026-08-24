# Joidy installer for Windows (PowerShell)
# Mirrors scripts/install.sh
$ErrorActionPreference = "Stop"

$Repo = "https://github.com/Axel-DaMage/joidy.git"
$Dir = if ($env:JOIDY_DIR) { $env:JOIDY_DIR } else { Join-Path $HOME "joidy" }

if (Test-Path $Dir) {
  Write-Host "Joidy already exists at $Dir"
  Write-Host "To update: cd $Dir ; git pull ; docker compose pull ; docker compose up -d"
  exit 1
}

Write-Host "Downloading Joidy to $Dir..."
git clone --depth 1 $Repo $Dir
Set-Location $Dir
Copy-Item .env.example .env

# ─── Install `joidy` CLI into ~/.local/bin ────────────────────────
$LocalBin = Join-Path $HOME ".local\bin"
$ConfigDir = Join-Path $HOME ".config\joidy"
$JoidyScript = Join-Path $Dir "scripts\joidy.ps1"

New-Item -ItemType Directory -Force -Path $LocalBin | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

# Persist the project path so the CLI survives renames/moves of the install.
Set-Content -Path (Join-Path $ConfigDir "path") -Value $Dir -NoNewline
Write-Host "✓ Project path saved to $ConfigDir\path"

# Copy the CLI script (overwrite any previous install).
Copy-Item $JoidyScript (Join-Path $LocalBin "joidy.ps1") -Force
Write-Host "✓ Installed 'joidy' CLI → $LocalBin\joidy.ps1"

# Create a joidy.cmd shim so users can type `joidy` without the .ps1 extension.
$CmdShim = Join-Path $LocalBin "joidy.cmd"
$CmdContent = "@`"%~dp0joidy.ps1`" %*"
Set-Content -Path $CmdShim -Value $CmdContent -Encoding ASCII
Write-Host "✓ Created 'joidy.cmd' shim → $CmdShim"

# ─── Ensure ~/.local/bin is in PATH ───────────────────────────────
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -and ($UserPath.Split(";") -contains $LocalBin)) {
  Write-Host "✓ $LocalBin already in user PATH"
} else {
  $NewPath = if ($UserPath) { "$UserPath;$LocalBin" } else { $LocalBin }
  [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
  Write-Host "✓ Added $LocalBin to user PATH (restart your shell to apply)"
}

Write-Host ""
Write-Host "Done!"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit $Dir\.env with your credentials"
Write-Host "  2. Restart your shell (so 'joidy' is in PATH), then run: joidy up"
Write-Host "  3. Open http://localhost:3000"
Write-Host ""
Write-Host "For updates: cd $Dir ; git pull ; docker compose pull ; joidy up"
