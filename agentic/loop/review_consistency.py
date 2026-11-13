#!/usr/bin/env python3
"""Reviewer-consistency check: review ONE fixed spec N times (no regeneration) and compare the verdicts.

    python agentic/loop/review_consistency.py <run_folder_for_plan> <spec.md> [N]

If the same spec is approved only some of the time, approval is reviewer noise and cannot be pushed to a
stable 80 % by changing the generator; then errors-per-spec is the honest measure of the review step.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from mudmut_core import env  # noqa: E402
env.ensure_environment()
from mudmut_core import agents, aio, chain, design  # noqa: E402
from spec_only import REQUIREMENTS, planned_module  # noqa: E402


def main(argv: list[str]) -> None:
    run, spec_file = Path(argv[0]), Path(argv[1])
    n = int(argv[2]) if len(argv) > 2 else 3
    swc = re.search(r"SWC_\w+?(?=_deepseek|_custom|$)", run.name).group(0)
    module = planned_module(run, swc)
    reqs = design.import_requirements(str(REQUIREMENTS)).requirement_set
    text = design.requirements_text(chain.requirements_for_module(reqs, module))
    spec = spec_file.read_text(encoding="utf-8")
    agents.apply_preset_with_report("deepseek")
    print(f"spec {spec_file.name}: {len(spec)} chars, reviewed {n} times", flush=True)
    seen: dict[str, int] = {}
    for i in range(n):
        t0 = time.time()
        rv = aio.run_sync(design.review_spec(module, text, spec))
        errs = [x.message for x in rv.issues if x.severity == "error"]
        print(f"review {i}: approved={rv.approved} coverage={rv.coverage_pct}% errors={rv.error_count} "
              f"warnings={rv.warning_count} uncovered={list(rv.uncovered_req_ids)} ({time.time() - t0:.0f}s)", flush=True)
        for e in errs:
            print(f"   error: {e[:170]}", flush=True)
            key = re.sub(r"[^a-z_]+", " ", e.lower())[:60]
            seen[key] = seen.get(key, 0) + 1
    print(f"distinct error texts: {len(seen)}; repeated in more than one review: "
          f"{sum(1 for v in seen.values() if v > 1)}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
