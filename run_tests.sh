#!/usr/bin/env bash
# ============================================================
#  MUD Tool - Run Tests (Linux/macOS)
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/python-sidecar"

source .venv/bin/activate 2>/dev/null || {
    echo "ERROR: Virtual environment not found. Run ./setup.sh first!"
    exit 1
}

echo ""
echo "Running MUD Tool Tests..."
echo "========================"
echo ""

pytest tests/ -v --tb=short "$@"
