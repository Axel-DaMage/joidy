<#
.SYNOPSIS
    Joidy Quick Start Script for Windows
.DESCRIPTION
    Sets up environment and starts all Joidy services with Docker.
    Equivalent to 'make start' but for Windows systems.
.EXAMPLE
    .\start.ps1
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Colors for output
$Green = "`e[0;32m"
$Yellow = "`e[0;33m"
$Blue = "`e[0;34m"
$Red = "`e[0;31m"
$Reset = "`e[0m"

function Write-Step($Message) {
    Write-Host "${Blue}Step ${script:step}:${Reset} $Message" -ForegroundColor Cyan
}

function Write-Success($Message) {
    Write-Host "${Green}✓${Reset} $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "${Yellow}⚠${Reset} $Message" -ForegroundColor Yellow
}

function Write-Error($Message) {
    Write-Host "${Red}✗${Reset} $Message" -ForegroundColor Red
}

function Test-Command($Command) {
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

$script:step = 0
$script:projectName = "joidy"

Write-Host ""
Write-Host "${Blue}═══ Joidy Quick Start (Windows) ═══${Reset}" -ForegroundColor Cyan
Write-Host ""

# Step 0: Check Docker
$script:step++
Write-Step "Checking Docker..."

if (-not (Test-Command "docker")) {
    Write-Error "Docker is not installed or not in PATH"
    Write-Host ""
    Write-Host "${Yellow}Please install Docker Desktop:${Reset}"
    Write-Host "  https://docs.docker.com/desktop/install/windows-install/"
    Write-Host ""
    Write-Host "After installation, restart your terminal and run this script again."
    exit 1
}

$dockerVersion = docker --version 2>&1
Write-Success "Docker: $dockerVersion"

# Check Docker Compose
$dockerComposeAvailable = $false
if (Test-Command "docker-compose") {
    $dockerComposeAvailable = $true
    Write-Success "Docker Compose (standalone): available"
} elseif ((docker compose version 2>&1) -match "Docker Compose") {
    $dockerComposeAvailable = $true
    Write-Success "Docker Compose (plugin): available"
}

if (-not $dockerComposeAvailable) {
    Write-Error "Docker Compose is not available"
    Write-Host "Please ensure Docker Desktop includes Docker Compose."
    exit 1
}

# Step 1: Setup directories and .env
$script:step++
Write-Step "Setting up environment..."

# Create data directories
$dirs = @("data\db", "data\uploads", "data\vault")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Success "Created data directories"

# Check/create .env
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Success "Created .env from .env.example"
    } else {
        Write-Error ".env.example not found"
        exit 1
    }
} else {
    Write-Success ".env already exists"
}

# Step 2: Check and update configuration
$script:step++
Write-Step "Checking configuration..."

# Load .env
$envVars = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        $envVars[$matches[1]] = $matches[2]
    }
}

# Check GEMINI_API_KEY
$geminiKey = $envVars["GEMINI_API_KEY"]
if ([string]::IsNullOrEmpty($geminiKey) -or $geminiKey -eq "your_gemini_api_key_here") {
    Write-Warn "GEMINI_API_KEY not set in .env"
    Write-Host "  Get your free API key at: https://aistudio.google.com/"
    Write-Host "  Then edit .env and add your key."
    Write-Host ""

    $continue = Read-Host "Continue without AI features? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        Write-Host "Aborted. Edit .env with your GEMINI_API_KEY and try again." -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Success "GEMINI_API_KEY configured"
}

# Check OBSIDIAN_VAULT_PATH
$vaultPath = $envVars["OBSIDIAN_VAULT_PATH"]
if ([string]::IsNullOrEmpty($vaultPath) -or $vaultPath -eq "/path/to/your/obsidian/vault") {
    Write-Warn "OBSIDIAN_VAULT_PATH not set"
    Write-Host "  Enter the full path to your Obsidian vault (e.g., C:\Users\You\Documents\Obsidian):"
    $newVaultPath = Read-Host "  Vault path (press Enter to skip)"
    if (-not [string]::IsNullOrEmpty($newVaultPath)) {
        $newVaultPath = $newVaultPath -replace '\\', '/'
        (Get-Content ".env") -replace 'OBSIDIAN_VAULT_PATH=.*', "OBSIDIAN_VAULT_PATH=$newVaultPath" | Set-Content ".env"
        Write-Success "Updated OBSIDIAN_VAULT_PATH in .env"
        $vaultPath = $newVaultPath
    }
} else {
    Write-Success "OBSIDIAN_VAULT_PATH: $vaultPath"
    if (Test-Path $vaultPath) {
        Write-Success "Vault directory exists"
    } else {
        Write-Warn "Vault directory does not exist yet"
    }
}

# Check/Generate SECRET_KEY
$secretKey = $envVars["SECRET_KEY"]
if ([string]::IsNullOrEmpty($secretKey) -or $secretKey -eq "change_this_to_a_random_secret_key") {
    # Generate a random secret
    $newSecret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 64 | ForEach-Object {[char]$_})
    (Get-Content ".env") -replace 'SECRET_KEY=.*', "SECRET_KEY=$newSecret" | Set-Content ".env"
    Write-Success "Generated new SECRET_KEY"
}

# Step 3: Start services
$script:step++
Write-Step "Starting services..."

# Check if compose files exist
if (-not (Test-Path "docker-compose.yml")) {
    Write-Error "docker-compose.yml not found"
    exit 1
}

$devCompose = "docker-compose.dev.yml"
if (-not (Test-Path $devCompose)) {
    Write-Warn "$devCompose not found, using default compose file"
    docker compose -p $script:projectName up --build -d
} else {
    docker compose -p $script:projectName -f docker-compose.yml -f $devCompose up --build -d
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start services"
    exit 1
}

# Final output
Write-Host ""
Write-Host "${Green}═══════════════════════════════════════════${Reset}" -ForegroundColor Green
Write-Host "${Green}  Joidy is running!${Reset}" -ForegroundColor Green
Write-Host "${Green}═══════════════════════════════════════════${Reset}" -ForegroundColor Green
Write-Host ""
Write-Host "  ${Green}Web App:${Reset}   http://localhost:3000"
Write-Host "  ${Green}API Docs:${Reset}  http://localhost:8000/docs"
Write-Host ""
Write-Host "To view logs:  docker compose logs -f"
Write-Host "To stop:       docker compose down"
Write-Host ""