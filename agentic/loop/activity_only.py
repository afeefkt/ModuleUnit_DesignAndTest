#!/usr/bin/env python3
"""Activity-step inner loop: re-run only the activity diagram + judge on a finished run's spec, N times.

    python agentic/loop/activity_only.py <run_folder> [N]
"""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mudmut_core import env, agents, aio, design, flow_quality  # noqa: E402
env.ensure_environment()
from mudtool.models.json_uml import GenerationResult  # noqa: E402

run = Path(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
spec = (run / "01_mud" / "mud_spec.md").read_text(encoding="utf-8")
swc = re.search(r"SWC_\w+", run.name).group(0)
ids = sorted(set(re.findall(r"REQ-[A-Z]+-\d+", spec)))
agents.apply_preset_with_report("deepseek")
judge = flow_quality.deepseek_judge()
for i in range(n):
    act = aio.run_sync(design.generate_activity([], spec, swc, use_ai=(len(sys.argv) <= 3)))
    q = flow_quality.evaluate(act, spec, ids, render=None, judge=judge)
    print(f"run {i}: score {q['score']} parts={q.get('parts')} missing_steps={len(q.get('missing_steps', []))}")
    j = q.get("judge") or {}
    for k in ("missing", "wrong"):
        for m in (j.get(k) or [])[:4]:
            print(f"   {k}: {str(m)[:220]}")
