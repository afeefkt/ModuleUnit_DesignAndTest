#!/usr/bin/env bash
# ============================================================
#  MUD Tool - Start Server (Linux/macOS)
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo " Starting MUD Tool Server..."
echo " Press Ctrl+C to stop."
echo ""

cd "$SCRIPT_DIR/python-sidecar"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo " ERROR: Virtual environment not found."
    echo " Run ./setup.sh first!"
    exit 1
fi

# Check .env
if [ ! -f ".env" ]; then
    echo " WARNING: No .env file found. Using defaults."
    echo " Run ./setup.sh or copy .env.example to .env"
    echo ""
fi

echo " ------------------------------------------------"
echo "  MUD Tool Sidecar v0.1.0"
echo "  Web UI:    http://127.0.0.1:8042/"
echo "  API Docs:  http://127.0.0.1:8042/docs"
echo "  Health:    http://127.0.0.1:8042/api/v1/health"
echo " ------------------------------------------------"
echo ""

python -m mudtool.main
