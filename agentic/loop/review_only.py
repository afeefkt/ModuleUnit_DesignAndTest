#!/usr/bin/env python3
"""Review-step inner loop: re-run only review_and_improve on a finished run's spec, N times, and score each.

    python agentic/loop/review_only.py <run_folder> [N]

The module (name, ASIL, runnables, requirement ids) and the requirement text come from the run's own
00_input/requirements.json and plan (state.json), so the step sees what the chain gave it.
Per run it prints: approved, coverage %, errors, warnings, whether the rewrite passes the spec check.
"""
import json, re, sys
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mudmut_core import env, agents, aio, design, spec_check  # noqa: E402
env.ensure_environment()

run = Path(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
spec = (run / "01_mud" / "mud_spec.md").read_text(encoding="utf-8")
swc = re.search(r"SWC_\w+", run.name).group(0)
ids = sorted(set(re.findall(r"REQ-[A-Z]+-\d+", spec)))
module = SimpleNamespace(swc_name=swc, asil="ASIL-D", req_ids=ids, runnables=re.findall(r"^###\s+(RE_\w+)", spec, re.M),
                         description="")
reqs = json.loads((run / "00_input" / "requirements.json").read_text(encoding="utf-8"))
rows = reqs if isinstance(reqs, list) else reqs.get("requirements", [])
text = "\n".join(f"[{r.get('req_id')}] {r.get('title', '')}\n  Description: {r.get('description', '')}"
                 for r in rows if r.get("req_id") in set(ids))
agents.apply_preset_with_report("deepseek")
for i in range(n):
    md, review = aio.run_sync(design.review_and_improve(module, text, spec, max_rounds=2))
    md = design.clean_spec_markdown(md)
    sc = spec_check.check_spec(md, swc, module.runnables)
    print(f"run {i}: approved={review.approved} coverage={review.coverage_pct}% errors={review.error_count} "
          f"warnings={review.warning_count} spec_gaps={spec_check.gap_count(sc)} usable={len(sc['usable'])}/{len(module.runnables)}")
    for iss in review.issues[:3]:
        print(f"   {iss.severity}: {iss.message[:200]}")
