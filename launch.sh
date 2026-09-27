#!/usr/bin/env bash
# MUD_MUT Control Center — one-command launch (Linux/macOS/Git-Bash).
# Starts Docker services (mud-tool + cpputest-rag + test-runner + Ollama),
# opens the Streamlit Control Center, and stops services on exit.
set -uo pipefail
cd "$(dirname "$0")"

# ── 1. Make sure the Docker engine is up ─────────────────────────────────────
if ! docker info >/dev/null 2>&1; then
  DD="/c/Program Files/Docker/Docker/Docker Desktop.exe"
  if [ -x "$DD" ]; then
    echo "[launch] Docker engine not running — starting Docker Desktop…"
    "$DD" >/dev/null 2>&1 &
  else
    echo "[launch] Docker engine not running — please start Docker."
  fi
  for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
fi
if ! docker info >/dev/null 2>&1; then
  echo "[launch] ERROR: Docker is still not reachable. Start Docker Desktop and re-run."
  echo "[launch]        (Continuing to Streamlit so you can see service status.)"
fi

# ── 2. Pick the Ollama mode ──────────────────────────────────────────────────
COMPOSE=(docker compose -f docker-compose.yml)
if curl -fs -o /dev/null http://localhost:11434/api/tags; then
  # Native Ollama already serves your pulled models — containers use it.
  echo "[launch] Native Ollama detected on :11434 — containers will use it."
else
  echo "[launch] No Ollama on the host — starting the bundled Ollama container."
  export DOCKER_OLLAMA_BASE=http://ollama:11434
  COMPOSE+=(--profile bundled-ollama)
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
    COMPOSE+=(-f docker-compose.gpu.yml)
    echo "[launch] NVIDIA GPU detected — bundled Ollama will use it."
  fi
fi

# ── 3. Start backend services ────────────────────────────────────────────────
echo "[launch] Starting Docker services (mud-tool, cpputest-rag)…"
if ! "${COMPOSE[@]}" up -d --build; then
  echo "[launch] WARNING: docker compose up failed — see the output above."
  echo "[launch]          Continuing to Streamlit anyway."
fi

# ── 4. Tear down on exit (Ctrl+C or normal exit) ────────────────────────────
cleanup() {
  echo ""
  echo "[launch] Stopping Docker services…"
  "${COMPOSE[@]}" down
}
trap cleanup EXIT INT TERM

# ── 5. Create launcher venv if needed ───────────────────────────────────────
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

# ── 6. Run Streamlit (blocking) ──────────────────────────────────────────────
echo "[launch] Starting MUD_MUT Control Center at http://localhost:8501"
echo "[launch] Press Ctrl+C to stop. Docker services will be shut down on exit."
streamlit run launcher/streamlit_app.py
