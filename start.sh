#!/bin/bash
# SodhiCable MES v4.0 — Start Script
# Usage: ./start.sh

cd "$(dirname "$0")"

# Load .env file if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

echo ""
echo "  SodhiCable MES v4.0"
echo "  Claude AI: Enabled"
echo ""

python app.py
