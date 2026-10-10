#!/usr/bin/env bash
# MUD_MUT — one-time setup (Linux / WSL). No Docker.
# Creates .venv, installs the in-process engine + Streamlit, and checks the
# C/C++ toolchain (CppUTest + lcov) and the Ollama models the defaults use.
set -uo pipefail
cd "$(dirname "$0")"

VENV=".venv"
PY="$(command -v python3 || command -v python)"

if [ ! -x "$VENV/bin/python" ]; then
  echo "[setup] Creating virtual environment…"
  "$PY" -m venv "$VENV" || { echo "[setup] venv failed — try: sudo apt-get install -y python3-venv" >&2; exit 1; }
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "[setup] Installing Python packages…"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -e "mud-tool/python-sidecar[dev]"
python -m pip install --quiet -r cpputest-rag/backend/requirements-native.txt
python -m pip install --quiet -r launcher/requirements.txt

echo "[setup] Checking the C/C++ toolchain…"
missing=""
for t in gcc g++ make lcov; do command -v "$t" >/dev/null 2>&1 || missing="$missing $t"; done
[ -f /usr/include/CppUTest/TestHarness.h ] || missing="$missing cpputest"
if [ -n "$missing" ]; then
  echo "[setup]   missing:$missing"
  echo "[setup]   install with:  sudo apt-get install -y build-essential cpputest lcov"
  echo "[setup]   (from Windows:  wsl -u root -e apt-get install -y build-essential cpputest lcov)"
else
  echo "[setup]   gcc, g++, make, CppUTest, lcov: OK"
fi

echo "[setup] Checking Ollama models used by the defaults…"
OLLAMA="${OLLAMA_HOST_URL:-http://localhost:11434}"
tags="$(curl -fs "$OLLAMA/api/tags" 2>/dev/null || true)"
if [ -z "$tags" ]; then
  echo "[setup]   Ollama not reachable at $OLLAMA — start Ollama, then re-run this check."
else
  # The models actually configured (mud-tool .env, root .env), with defaults.
  cfg() { grep -h "^$1=" mud-tool/python-sidecar/.env .env 2>/dev/null | head -n1 | cut -d= -f2 | sed 's/[[:space:]].*//'; }
  models="$(cfg MUD_OPENAI_MODEL || true) $(cfg MUD_PIPELINE_REVIEWER_MODEL || true) $(cfg GEN_MODEL || true) $(cfg MUD_GUIDELINES_EMBED_MODEL || true) $(cfg EMBED_MODEL || true)"
  [ -n "${models// /}" ] || models="qwen3:8b deepseek-r1:7b qwen2.5:7b nomic-embed-text all-minilm"
  for m in $models; do
    if echo "$tags" | grep -q "\"$m"; then echo "[setup]   $m: OK"
    else echo "[setup]   $m: MISSING  →  ollama pull $m"; fi
  done
fi

echo ""
echo "[setup] Done. Start the platform:  ./launch.sh   (Windows: launch.bat)"
