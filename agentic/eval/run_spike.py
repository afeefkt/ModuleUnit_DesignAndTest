#!/usr/bin/env python3
"""Spike evaluation: can a local model drive the mud-designer tool loop?

Runs `opencode run --agent mud-designer` across models × runnables, then
deterministically re-validates the produced activity.json with the same CLI the
agent uses. Writes `agentic/eval/results.md` with the go/no-go numbers.

Usage:
    MUDMUT_RUNS=5 python agentic/eval/run_spike.py

Env:
    MUDMUT_RUNS            runs per (model, runnable) cell  (default 5)
    MUDMUT_TIMEOUT         seconds per run                 (default 600)
    MUDMUT_OLLAMA_BASE_URL Ollama base URL                 (default http://localhost:11434/v1)
    MUDMUT_CONTROL_MODEL   cloud control model             (default deepseek/deepseek-flash)
    MUDMUT_MODELS          comma-separated local models    (default qwen3:8b-ctx16384,qwen3.5:9b-ctx16384)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AGENT = "mud-designer"
CLI = REPO / "agentic" / "tools" / "mudmut_cli.py"
RUNS_DIR = REPO / "agentic" / "runs"
RESULTS_PATH = REPO / "agentic" / "eval" / "results.md"

RUNS = int(os.environ.get("MUDMUT_RUNS", "5"))
TIMEOUT = int(os.environ.get("MUDMUT_TIMEOUT", "600"))
OLLAMA_BASE_URL = os.environ.get("MUDMUT_OLLAMA_BASE_URL", "http://localhost:11434/v1")
CONTROL_MODEL = os.environ.get("MUDMUT_CONTROL_MODEL", "deepseek/deepseek-flash")
LOCAL_MODELS = [
    f"ollama/{m.strip()}" for m in os.environ.get(
        "MUDMUT_MODELS", "qwen3:8b-ctx16384,qwen3.5:9b-ctx16384"
    ).split(",") if m.strip()
]
RUNNABLES = ["RE_EstimateSOC", "RE_MonitorSafety"]

PROMPT = "Design the activity flow for {runnable} from inputs/requirements/samples/bms_requirements.csv. Use run id '{run_id}'."


def _find_strings(obj, key="command", acc=None):
    """Recursively collect all string values under `key` in a JSON structure."""
    if acc is None:
        acc = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                acc.append(v)
            else:
                _find_strings(v, key, acc)
    elif isinstance(obj, list):
        for item in obj:
            _find_strings(item, key, acc)
    return acc


def run_agent(model: str, runnable: str, run_id: str) -> dict:
    prompt = PROMPT.format(runnable=runnable, run_id=run_id)
    env = dict(os.environ)
    env["OLLAMA_BASE_URL"] = OLLAMA_BASE_URL
    # Ensure the venv `python` (with mudtool deps) is what the agent invokes.
    env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            ["opencode", "run", "--agent", AGENT, "--model", model, "--format", "json", prompt],
            capture_output=True, text=True, timeout=TIMEOUT, env=env, cwd=REPO,
        )
    except subprocess.TimeoutExpired:
        return {"model": model, "runnable": runnable, "run_id": run_id,
                "timeout": True, "wall_s": round(TIMEOUT)}

    wall = round(time.monotonic() - t0, 1)

    commands: list[str] = []
    tool_errors = 0
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        commands.extend(_find_strings(evt, "command"))
        # count tool-level errors surfaced in the stream
        if _contains_error(evt):
            tool_errors += 1

    validate_calls = sum(1 for c in commands if "validate-activity" in c)
    return {
        "model": model, "runnable": runnable, "run_id": run_id,
        "timeout": False, "wall_s": wall,
        "validate_calls": validate_calls,
        "tool_errors": tool_errors,
    }


def _contains_error(obj) -> bool:
    if isinstance(obj, dict):
        if obj.get("type") in ("tool_error",) or obj.get("status") == "error":
            return True
        if isinstance(obj.get("error"), str) and obj.get("error"):
            return True
        return any(_contains_error(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_error(x) for x in obj)
    return False


def deterministic_validate(run_id: str) -> dict | None:
    """Re-validate the agent's final activity.json with the same CLI."""
    activity = RUNS_DIR / run_id / "activity.json"
    if not activity.exists():
        return None
    try:
        proc = subprocess.run(
            [sys.executable, str(CLI), "validate-activity", str(activity), "--run", run_id],
            capture_output=True, text=True, timeout=120, cwd=REPO,
        )
        return json.loads(proc.stdout)
    except Exception:
        return None


def run_cell(model: str, runnable: str, label: str) -> list[dict]:
    rows = []
    for i in range(RUNS):
        run_id = f"eval-{label}-{runnable}-{i}"
        row = run_agent(model, runnable, run_id)
        v = deterministic_validate(run_id)
        row["valid"] = v.get("valid") if v else None
        row["error_count"] = v.get("error_count") if v else None
        rows.append(row)
    return rows


def summarize(rows: list[dict]) -> dict:
    finished = [r for r in rows if not r.get("timeout")]
    clean = [r for r in finished if r.get("valid") is True]
    iters = [r.get("validate_calls", 0) for r in finished]
    walls = [r.get("wall_s", 0) for r in finished]
    return {
        "runs": len(rows),
        "finished": len(finished),
        "timeouts": len(rows) - len(finished),
        "validator_clean": len(clean),
        "clean_pct": round(100 * len(clean) / max(len(finished), 1)),
        "median_fix_iters": _median(iters),
        "median_wall_s": _median(walls),
    }


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def main() -> int:
    all_cells: dict[str, dict] = {}
    local_finished = 0
    local_clean = 0
    local_walls: list[float] = []

    for model in LOCAL_MODELS:
        for runnable in RUNNABLES:
            label = model.split("/")[-1].split(":")[0]
            rows = run_cell(model, runnable, label)
            s = summarize(rows)
            all_cells[f"{model} :: {runnable}"] = s
            local_finished += s["finished"]
            local_clean += s["validator_clean"]
            local_walls.extend(r["wall_s"] for r in rows if not r.get("timeout"))

    # Cloud control: sample data only, one runnable, fewer runs.
    ctrl_rows = run_cell(CONTROL_MODEL, RUNNABLES[0], "control")
    all_cells[f"{CONTROL_MODEL} :: {RUNNABLES[0]} (control)"] = summarize(ctrl_rows)

    lines = ["# MUD_MUT agentic spike — results", "",
             f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", "",
             "| cell | runs | finished | timeouts | clean | clean% | median fix-iters | median wall(s) |",
             "|---|---|---|---|---|---|---|---|"]
    for cell, s in all_cells.items():
        lines.append(
            f"| {cell} | {s['runs']} | {s['finished']} | {s['timeouts']} | "
            f"{s['validator_clean']} | {s['clean_pct']}% | {s['median_fix_iters']} | {s['median_wall_s']} |"
        )

    clean_pct = round(100 * local_clean / max(local_finished, 1))
    median_wall = _median(local_walls)
    go = local_finished > 0 and clean_pct >= 80 and median_wall < 300
    lines += ["", "## Go / no-go (local models, all runs)",
              f"- finished runs: {local_finished}",
              f"- validator-clean: {local_clean} ({clean_pct}%)",
              f"- median wall time: {median_wall}s",
              f"- **verdict: {'GO' if go else 'NO-GO'}** (GO = clean >= 80% of finished, median < 300s)",
              "",
              "NO-GO fallback: keep the CLI tools and use the deterministic in-product state",
              "machine, where the LLM makes only narrow schema-constrained calls."]
    RESULTS_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
