# Demo script for Windows PowerShell
# One-command demo setup

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RCA System Demo Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
try {
    docker ps | Out-Null
    Write-Host "[OK] Docker is running" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check if Python is available
Write-Host "Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[OK] $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH" -ForegroundColor Red
    exit 1
}

# Check if required Python packages are installed
Write-Host "Checking Python dependencies..." -ForegroundColor Yellow
$requiredPackages = @("aiohttp", "asyncpg")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    try {
        python -c "import $package" 2>&1 | Out-Null
        Write-Host "[OK] $package is installed" -ForegroundColor Green
    } catch {
        Write-Host "[WARNING] $package is not installed" -ForegroundColor Yellow
        $missingPackages += $package
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Host "Installing missing packages..." -ForegroundColor Yellow
    foreach ($package in $missingPackages) {
        pip install $package
    }
}

# Start services
Write-Host ""
Write-Host "Starting Docker services..." -ForegroundColor Yellow
docker compose up -d

Write-Host "Waiting for services to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Check service health
Write-Host "Checking service health..." -ForegroundColor Yellow
$maxRetries = 12
$retryCount = 0
$healthy = $false

while ($retryCount -lt $maxRetries -and -not $healthy) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
        $data = $response.Content | ConvertFrom-Json
        if ($data.status -eq "healthy") {
            $healthy = $true
            Write-Host "[OK] All services are healthy" -ForegroundColor Green
        } else {
            Write-Host "[WAIT] Services starting... ($($retryCount + 1)/$maxRetries)" -ForegroundColor Yellow
            Start-Sleep -Seconds 5
            $retryCount++
        }
    } catch {
        Write-Host "[WAIT] Services starting... ($($retryCount + 1)/$maxRetries)" -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        $retryCount++
    }
}

if (-not $healthy) {
    Write-Host "[WARNING] Services may not be fully ready. Check logs with: docker compose logs" -ForegroundColor Yellow
}

# Seed demo data
Write-Host ""
Write-Host "Seeding demo data..." -ForegroundColor Yellow
python scripts/seed_demo_data.py

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Demo Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access the UI at: http://localhost:3001" -ForegroundColor Green
Write-Host "API Docs at: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "To view logs: docker compose logs -f" -ForegroundColor Yellow
Write-Host "To stop services: docker compose down" -ForegroundColor Yellow




