#!/bin/bash
# Demo script for Linux/Mac
# One-command demo setup

set -e

echo "========================================"
echo "RCA System Demo Setup"
echo "========================================"
echo ""

# Check if Docker is running
echo "Checking Docker..."
if ! docker ps > /dev/null 2>&1; then
    echo "[ERROR] Docker is not running. Please start Docker."
    exit 1
fi
echo "[OK] Docker is running"

# Check if Python is available
echo "Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo "[OK] $PYTHON_VERSION"

# Check if required Python packages are installed
echo "Checking Python dependencies..."
REQUIRED_PACKAGES=("aiohttp" "asyncpg")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! python3 -c "import $package" 2>/dev/null; then
        echo "[WARNING] $package is not installed"
        MISSING_PACKAGES+=("$package")
    else
        echo "[OK] $package is installed"
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "Installing missing packages..."
    pip3 install "${MISSING_PACKAGES[@]}"
fi

# Start services
echo ""
echo "Starting Docker services..."
docker compose up -d

echo "Waiting for services to be healthy..."
sleep 15

# Check service health
echo "Checking service health..."
MAX_RETRIES=12
RETRY_COUNT=0
HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$HEALTHY" = false ]; do
    if curl -s http://localhost:8000/health | grep -q '"status":"healthy"'; then
        HEALTHY=true
        echo "[OK] All services are healthy"
    else
        echo "[WAIT] Services starting... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
        sleep 5
        RETRY_COUNT=$((RETRY_COUNT + 1))
    fi
done

if [ "$HEALTHY" = false ]; then
    echo "[WARNING] Services may not be fully ready. Check logs with: docker compose logs"
fi

# Seed demo data
echo ""
echo "Seeding demo data..."
python3 scripts/seed_demo_data.py

echo ""
echo "========================================"
echo "Demo Setup Complete!"
echo "========================================"
echo ""
echo "Access the UI at: http://localhost:3001"
echo "API Docs at: http://localhost:8000/docs"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop services: docker compose down"




