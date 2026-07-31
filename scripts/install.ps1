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

Write-Host ""
Write-Host "Done!"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Edit $Dir\.env with your credentials"
Write-Host "  2. Run: cd $Dir ; docker compose up -d"
Write-Host "  3. Open http://localhost:3000"
Write-Host ""
Write-Host "For updates: cd $Dir ; git pull ; docker compose pull ; docker compose up -d"
