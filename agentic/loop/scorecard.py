#!/usr/bin/env python3
"""Per-step quality scorecard (0-100) for one run folder, in app execution order.

    python agentic/loop/scorecard.py <run_folder_or_snapshot> [--json]

Every number is computed from the artifacts the tool already wrote; nothing is estimated.
MUD steps: spec -> review -> activity.  Bridge: code (compilable gate).  MUT steps: tests -> coverage.
Chain score = mean of the step scores.  Target per step and for the chain: >= 80.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TARGET = 80


def _j(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def score_plan(folder: Path) -> tuple[float, str]:
    """Plan: every requirement assigned to a module, and enough runnables per module (>= 1 per 3 requirements)."""
    log = folder / "llm_log.jsonl"
    if not log.exists():
        return 0.0, "no llm_log.jsonl"
    modules = None
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("stage") == "plan" and e.get("response"):
            r = e["response"]
            try:
                modules = json.loads(r[r.index("{"):r.rindex("}") + 1]).get("modules")
            except ValueError:
                modules = None
            break
    if not modules:
        return 0.0, "no plan response"
    dens = []
    for m in modules:
        need = max(2, -(-len(m.get("req_ids", [])) // 3) + 1)          # RE_Init + ceil(reqs/3)
        dens.append(min(1.0, len(m.get("runnables", [])) / need))
    s = 100.0 * sum(dens) / len(dens)
    thin = [m["swc_name"] for m, d in zip(modules, dens) if d < 0.6]
    return _clamp(s), f"{len(modules)} modules, thin: {thin}"


def score_spec(folder: Path) -> tuple[float, str]:
    sc = _j(folder / "01_mud" / "spec_check.json")
    if not sc:
        return 0.0, "no spec_check.json"
    n = max(1, sc.get("runnables", 0))
    s = 100.0 * len(sc.get("usable", [])) / n
    s -= 10 * len(sc.get("problems", [])) + 10 * len(sc.get("placeholder", [])) + 10 * len(sc.get("empty", []))
    s -= 5 * len(sc.get("never_set", {})) + 5 * len(sc.get("undescribed_helpers", {}))
    return _clamp(s), f"{len(sc.get('usable', []))}/{n} runnables usable, {len(sc.get('problems', []))} problems"


def score_review(folder: Path) -> tuple[float, str]:
    rv = _j(folder / "01_mud" / "review.json")
    if not rv:
        return 0.0, "no review.json"
    issues = rv.get("issues", [])
    err = sum(1 for i in issues if i.get("severity") == "error")
    warn = sum(1 for i in issues if i.get("severity") == "warning")
    s = float(rv.get("coverage_pct", 0)) - 15 * err - 3 * warn
    if not rv.get("approved"):
        s = min(s, 60.0)
    return _clamp(s), f"approved={rv.get('approved')} coverage={rv.get('coverage_pct')}% errors={err} warnings={warn}"


def score_activity(folder: Path) -> tuple[float, str]:
    rj = _j(folder / "run.json") or {}
    q = rj.get("activity_quality") or {}
    if not q:
        return 0.0, "no activity_quality"
    return float(q.get("score", 0)), f"parts={q.get('parts')}"


def score_code(folder: Path) -> tuple[float, str]:
    c = _j(folder / "02_code" / "compilability.json")
    if not c:
        return 0.0, "no compilability.json"
    tot = max(1, c.get("total_statements", 0))
    s = 100.0 * c.get("kept_statements", 0) / tot
    s -= 10 * c.get("logic_stubbed", 0) + 5 * len(c.get("never_assigned", [])) + 5 * c.get("dropped_arguments", 0)
    if not c.get("compile_ok"):
        s = min(s, 30.0)
    return _clamp(s), (f"kept {c.get('kept_statements')}/{tot}, logic_stubbed={c.get('logic_stubbed')}, "
                       f"compile_ok={c.get('compile_ok')}")


def score_tests(folder: Path) -> tuple[float, str]:
    rj = _j(folder / "run.json") or {}
    t = (rj.get("tests") or {}).get("junit") or {}
    n = t.get("tests", 0)
    if not n:
        return 0.0, "no junit results"
    pct = 100.0 * t.get("passed", 0) / n
    quarantined = len((rj.get("tests") or {}).get("quarantined_tests", []))
    return _clamp(pct - 5 * quarantined), f"{t.get('passed')}/{n} pass, quarantined={quarantined}"


def score_coverage(folder: Path) -> tuple[float, str]:
    info = folder / "03_mut" / "coverage.info"
    if not info.exists():
        return 0.0, "no coverage.info"
    text = info.read_text(encoding="utf-8", errors="replace")
    brh = brf = lh = lf = 0
    for m in re.finditer(r"^BRDA:\d+,\d+,\d+,(\S+)$", text, re.M):
        brf += 1
        brh += 0 if m.group(1) in ("-", "0") else 1
    for m in re.finditer(r"^DA:\d+,(\d+)", text, re.M):
        lf += 1
        lh += 1 if int(m.group(1)) > 0 else 0
    if brf == 0 and lf == 0:
        return 0.0, "coverage.info has no data"
    parts = []
    if lf:
        parts.append(100.0 * lh / lf)
    if brf:
        parts.append(100.0 * brh / brf)
    return _clamp(sum(parts) / len(parts)), f"lines {lh}/{lf}, branches {brh}/{brf}"


STEPS = [
    ("0 plan runnables", score_plan),
    ("1 MUD  spec", score_spec),
    ("2 MUD  review", score_review),
    ("3 MUD  activity", score_activity),
    ("4 code compilable", score_code),
    ("5 MUT  tests pass", score_tests),
    ("6 MUT  coverage", score_coverage),
]


def scorecard(folder: Path) -> dict:
    rows = []
    for name, fn in STEPS:
        s, note = fn(folder)
        rows.append({"step": name, "score": round(s, 1), "note": note})
    chain = round(sum(r["score"] for r in rows) / len(rows), 1)
    return {"folder": str(folder), "steps": rows, "chain": chain, "target": TARGET}


def render(card: dict) -> str:
    out = [f"{card['folder']}"]
    for r in card["steps"]:
        bar = "#" * int(r["score"] // 5)
        flag = "ok " if r["score"] >= card["target"] else "LOW"
        out.append(f"  {flag} {r['step']:<20} {r['score']:>5.1f} {bar:<20} {r['note']}")
    out.append(f"  CHAIN {card['chain']} (target {card['target']})")
    return "\n".join(out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    card = scorecard(Path(args[0]))
    print(json.dumps(card, indent=1) if "--json" in sys.argv else render(card))
