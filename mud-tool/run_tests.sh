#!/usr/bin/env bash
# ============================================================
#  MUD Tool - Test Runner
#  Run from repository root: ./run_tests.sh [quality|unit|all|coverage|live]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIDECAR_DIR="$SCRIPT_DIR/python-sidecar"
cd "$SIDECAR_DIR"
export PYTHONDONTWRITEBYTECODE=1

if [[ -x ".venv/bin/python" ]]; then
    PYTHON_EXE=".venv/bin/python"
elif [[ -x ".venv/Scripts/python.exe" ]]; then
    PYTHON_EXE=".venv/Scripts/python.exe"
else
    echo "ERROR: Virtual environment not found. Run ./setup.sh or setup.bat first."
    exit 1
fi

MODE="${1:-quality}"
shift || true

QUALITY_TESTS=(
    tests/unit/test_activity_pipeline_cfg.py
    tests/unit/test_api_routes.py
    tests/unit/test_web_generation_quality_ui.py
)

echo ""
echo "Running MUD Tool tests"
echo "======================"
echo "Mode: $MODE"
echo ""

case "$MODE" in
    quality)
        "$PYTHON_EXE" -m pytest "${QUALITY_TESTS[@]}" -q "$@"
        ;;
    unit)
        "$PYTHON_EXE" -m pytest tests/unit -q "$@"
        ;;
    all)
        "$PYTHON_EXE" -m pytest tests -q -k "not live" "$@"
        ;;
    coverage)
        "$PYTHON_EXE" -m pytest tests -q -k "not live" --cov=mudtool --cov-report=term-missing "$@"
        ;;
    live)
        "$PYTHON_EXE" -m pytest tests -q "$@"
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Usage: ./run_tests.sh [quality|unit|all|coverage|live]"
        exit 2
        ;;
esac
