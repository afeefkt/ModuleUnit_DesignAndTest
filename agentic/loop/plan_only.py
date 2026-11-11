#!/usr/bin/env python3
"""Plan-step inner loop: run only the module planner N times on the AEB requirements, print density scores."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mudmut_core import env, agents, aio, design  # noqa: E402
env.ensure_environment()
REQ = ROOT / "inputs/requirements_hardened/aeb/aeb_requirements_hardened.csv"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
agents.apply_preset_with_report("deepseek")
text = design.requirements_text(design.import_requirements(str(REQ)).requirement_set)
for i in range(n):
    plan = aio.run_sync(design.plan_modules(text))
    dens = []
    for m in plan.modules:
        need = max(2, -(-len(m.req_ids) // 3) + 1)
        dens.append(min(1.0, len(m.runnables) / need))
    ids = {r for m in plan.modules for r in m.req_ids}
    print(f"run {i}: score {100*sum(dens)/len(dens):.1f} modules={len(plan.modules)} reqs_assigned={len(ids)}")
    print("   ", {m.swc_name: len(m.runnables) for m in plan.modules})
