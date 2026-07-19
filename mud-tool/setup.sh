#!/usr/bin/env bash
# ============================================================
#  MUD Tool - Linux/macOS Setup Script
#  AI-Assisted AUTOSAR Module & Unit Design
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "================================================================"
echo " MUD Tool Setup - AUTOSAR Module & Unit Design"
echo "================================================================"
echo ""

# ── Check Python ──────────────────────────────────────
echo "[1/6] Checking Python installation..."
if ! command -v python3 &>/dev/null; then
    echo " ERROR: Python 3 not found."
    echo " Install: sudo apt install python3 python3-venv python3-pip"
    echo "    or:   brew install python3"
    exit 1
fi
PYVER=$(python3 --version)
echo " Found $PYVER"

# ── Create virtual environment ────────────────────────
echo ""
echo "[2/6] Creating Python virtual environment..."
cd "$SCRIPT_DIR/python-sidecar"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo " Virtual environment created at python-sidecar/.venv"
else
    echo " Virtual environment already exists, skipping."
fi

# ── Activate venv and install dependencies ────────────
echo ""
echo "[3/6] Installing Python dependencies..."
source .venv/bin/activate

pip install --upgrade pip >/dev/null 2>&1
pip install -e ".[dev]"
echo " All Python dependencies installed."

# ── Setup .env file ───────────────────────────────────
echo ""
echo "[4/6] Setting up configuration..."
cd "$SCRIPT_DIR/python-sidecar"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo " Created .env from template."
    echo " IMPORTANT: Edit python-sidecar/.env and add your ANTHROPIC API key!"
    echo ""
    echo " Get your API key from: https://console.anthropic.com/settings/keys"
else
    echo " .env already exists, skipping."
fi

# ── Create output directories ─────────────────────────
echo ""
echo "[5/6] Creating data directories..."
cd "$SCRIPT_DIR"
mkdir -p data output
echo " Directories ready."

# ── Check Java (optional) ────────────────────────────
echo ""
echo "[6/6] Checking Java installation (optional)..."
if command -v java &>/dev/null; then
    JAVAVER=$(java -version 2>&1 | head -1)
    echo " Found $JAVAVER"
    if command -v mvn &>/dev/null; then
        echo " Maven found. Build plugin: cd modelio-plugin && mvn compile"
    else
        echo " Maven not found. Install to build the Modelio plugin."
    fi
else
    echo " Java not found. Modelio plugin requires Java 17+."
    echo " The Python sidecar works standalone without Java."
fi

echo ""
echo "================================================================"
echo " Setup Complete!"
echo "================================================================"
echo ""
echo " NEXT STEPS:"
echo ""
echo " 1. Edit your API key:"
echo "    nano python-sidecar/.env"
echo "    (Set MUD_ANTHROPIC_API_KEY=sk-ant-your-actual-key)"
echo ""
echo " 2. Start the server:"
echo "    ./run.sh"
echo ""
echo " 3. Open the API docs in your browser:"
echo "    http://127.0.0.1:8042/docs"
echo ""
