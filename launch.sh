#!/usr/bin/env bash
# MUD_MUT — one-command launch (Linux / WSL). No Docker.
# Activates the .venv and starts the Streamlit platform.
set -uo pipefail
cd "$(dirname "$0")"

VENV=".venv"

if [ ! -x "$VENV/bin/python" ]; then
  echo "[launch] No .venv found. Run ./setup.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "[launch] Starting MUD_MUT at http://localhost:8501"
echo "[launch] Press Ctrl+C to stop."
# python -m: works even when the venv's `streamlit` console script is missing.
exec python -m streamlit run launcher/streamlit_app.py --server.headless true --server.address localhost
