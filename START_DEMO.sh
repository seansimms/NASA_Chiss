#!/bin/bash
# Chiss NASA Demo - One Command Startup
# This script starts the complete dashboard with Docker Compose

echo "🚀 Starting Chiss Exoplanet Discovery Dashboard for NASA Demo"
echo "============================================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop:"
    echo "   https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "✅ Docker is ready"
echo ""

# Stop any existing containers
echo "🧹 Cleaning up any existing containers..."
docker-compose down 2>/dev/null || true
echo ""

# Build and start
echo "🔨 Building containers (this may take 3-5 minutes on first run)..."
docker-compose up --build -d

echo ""
echo "⏳ Waiting for services to be healthy..."
echo ""

# Wait for backend
MAX_WAIT=60
WAIT_TIME=0
until curl -sf http://localhost:8001/api/health > /dev/null 2>&1; do
    if [ $WAIT_TIME -ge $MAX_WAIT ]; then
        echo "❌ Backend failed to start within ${MAX_WAIT} seconds"
        echo ""
        echo "Check logs with: docker-compose logs backend"
        exit 1
    fi
    echo -n "."
    sleep 2
    WAIT_TIME=$((WAIT_TIME + 2))
done

echo ""
echo ""
echo "✅ Services are ready!"
echo ""
echo "================================================================"
echo "🌟 Chiss Dashboard is now running!"
echo "================================================================"
echo ""
echo "📊 Open in your browser:"
echo "   👉 http://localhost:5173"
echo ""
echo "🔧 API Health Check:"
echo "   http://localhost:8001/api/health"
echo ""
echo "📋 Useful Commands:"
echo "   View logs:    docker-compose logs -f"
echo "   Stop demo:    docker-compose down"
echo "   Restart:      docker-compose restart"
echo ""
echo "🎯 Try the Demo:"
echo "   1. Click 'Discoveries' tab"
echo "   2. Enter TIC ID: 307210830"
echo "   3. Period Range: 20-100 days"
echo "   4. Click 'Start Search'"
echo "   5. Watch the live logs!"
echo ""
echo "================================================================"
echo ""

