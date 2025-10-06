#!/bin/bash
# Stop the Chiss NASA Demo

echo "🛑 Stopping Chiss Dashboard..."
docker-compose down

echo ""
echo "✅ Dashboard stopped"
echo ""
echo "To start again, run: ./START_DEMO.sh"
echo ""

