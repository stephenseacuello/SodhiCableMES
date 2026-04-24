#!/bin/bash
# SodhiCable MES v4.0 — Start Script
# Usage: ./start.sh

# Set your Anthropic API key for Claude AI features (optional)
# export ANTHROPIC_API_KEY="your-key-here"

cd "$(dirname "$0")"

echo ""
echo "  SodhiCable MES v4.0"
echo "  Claude AI: Enabled"
echo ""

python app.py
