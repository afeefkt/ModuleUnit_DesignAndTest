#!/usr/bin/env bash
# MUD_MUT Control Center — one-command launch (Linux/macOS/Git-Bash).
# Starts Docker services (mud-tool + cpputest-rag + test-runner + Ollama),
# opens the Streamlit Control Center, and stops services on exit.
set -uo pipefail
cd "$(dirname "$0")"

# ── 1. Start backend services ────────────────────────────────────────────────
echo "[launch] Starting Docker services (mud-tool, cpputest-rag, ollama)…"
if ! docker compose up -d --build; then
  echo "[launch] WARNING: docker compose up failed. Is Docker running?"
  echo "[launch]          Continuing to Streamlit anyway."
fi

# ── 2. Tear down on exit (Ctrl+C or normal exit) ────────────────────────────
cleanup() {
  echo ""
  echo "[launch] Stopping Docker services…"
  docker compose down
}
trap cleanup EXIT INT TERM

# ── 3. Create launcher venv if needed ───────────────────────────────────────
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

# ── 4. Run Streamlit (blocking) ──────────────────────────────────────────────
echo "[launch] Starting MUD_MUT Control Center at http://localhost:8501"
echo "[launch] Press Ctrl+C to stop. Docker services will be shut down on exit."
streamlit run launcher/streamlit_app.py
