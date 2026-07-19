#!/usr/bin/env bash
# MUD_MUT Control Center — one-command launch (Linux/macOS/Git-Bash).
# Creates a local venv for the launcher, installs Streamlit, and starts the UI.
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv-launcher"
if [ ! -d "$VENV" ]; then
  echo "[launch] Creating launcher venv…"
  python -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/Scripts/activate" 2>/dev/null || source "$VENV/bin/activate"

echo "[launch] Installing Streamlit…"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r launcher/requirements.txt

echo "[launch] Starting MUD_MUT Control Center at http://localhost:8501"
exec streamlit run launcher/streamlit_app.py
