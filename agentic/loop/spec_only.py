#!/usr/bin/env python3
"""Spec-step inner loop: regenerate ONLY the MUD spec N times from a finished run's plan, then review it once.

    python agentic/loop/spec_only.py <run_folder> [N] [--no-review]

Reuses the run's plan (no planner call), gives the spec step the same per-module requirement text the
chain gives it, and prints per sample: runnables, deterministic spec gaps, IRVs/P-ports with more than one
writer runnable (free check), and - unless --no-review - one review verdict (approved, coverage, errors).
Much cheaper than a full chain: no activity, code or test generation.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from mudmut_core import env  # noqa: E402
env.ensure_environment()
from mudmut_core import agents, aio, chain, design, spec_check  # noqa: E402
from mudtool.ai.module_planner import ModuleInfo  # noqa: E402
from mudtool.ai.mud_activity_context import build_mud_activity_context  # noqa: E402

REQUIREMENTS = ROOT / "inputs/requirements_hardened/aeb/aeb_requirements_hardened.csv"
_WRITE_RE = re.compile(r"\b(?:Rte_IrvWrite\s*\(\s*(IRV_\w+)|Rte_I?Write\s*\(\s*(PP_\w+))")


def multi_writers(spec_md: str, swc: str) -> dict[str, list[str]]:
    """IRV / P-port -> runnables (other than RE_Init) that write it, for those with more than one writer."""
    writers: dict[str, set[str]] = {}
    for r in build_mud_activity_context(spec_md, swc).runnables:
        if r.name == "RE_Init":
            continue
        code = re.sub(r"//[^\n]*", "", r.functional_description or "")
        for m in _WRITE_RE.finditer(code):
            writers.setdefault(next(g for g in m.groups() if g), set()).add(r.name)
    return {k: sorted(v) for k, v in writers.items() if len(v) > 1}


def planned_module(run: Path, swc: str) -> ModuleInfo:
    for line in (run / "llm_log.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("stage") == "plan" and e.get("response"):
            r = e["response"]
            for m in json.loads(r[r.index("{"):r.rindex("}") + 1]).get("modules", []):
                if m.get("swc_name") == swc:
                    return ModuleInfo.from_dict(m)
    raise SystemExit(f"no plan for {swc} in {run}")


def main(argv: list[str]) -> None:
    run = Path(argv[0])
    n = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 3
    do_review = "--no-review" not in argv
    swc = re.search(r"SWC_\w+?(?=_deepseek|_custom|$)", run.name).group(0)
    module = planned_module(run, swc)
    reqs = design.import_requirements(str(REQUIREMENTS)).requirement_set
    module_reqs = chain.requirements_for_module(reqs, module)
    text = design.requirements_text(module_reqs)
    agents.apply_preset_with_report("deepseek")
    print(f"{swc}: {len(module.runnables)} planned runnables, {module_reqs.count} requirements", flush=True)
    for i in range(n):
        t0 = time.time()
        spec = design.clean_spec_markdown(aio.run_sync(design.generate_mud_spec(module, text)))
        sc = spec_check.check_spec(spec, swc, module.runnables)
        repair_note = ""
        if spec_check.gap_count(sc):            # the chain's targeted repair, kept only when it is better
            fixed = design.clean_spec_markdown(aio.run_sync(design.repair_spec_from_check(module, text, spec, sc)))
            sc2 = spec_check.check_spec(fixed, swc, module.runnables) if fixed else None
            if sc2 and spec_check.gap_count(sc2) < spec_check.gap_count(sc) and not spec_check.rewrite_problem(spec, fixed):
                repair_note = f" (repair kept: gaps {spec_check.gap_count(sc)} -> {spec_check.gap_count(sc2)})"
                spec, sc = fixed, sc2
            else:
                repair_note = f" (repair discarded: gaps {spec_check.gap_count(sc)} -> " \
                              f"{spec_check.gap_count(sc2) if sc2 else '-'})"
        mw = multi_writers(spec, swc)
        line = (f"sample {i}: {len(spec)} chars, usable {len(sc['usable'])}/{sc['runnables']}, "
                f"gaps {spec_check.gap_count(sc)}{repair_note}, multi-writer {len(mw)} {mw or ''}")
        if do_review and "--improve" in argv:     # the chain's review loop (review -> runnable repair -> review)
            improved, rv = aio.run_sync(design.review_and_improve(module, text, spec, max_rounds=2))
            spec = design.clean_spec_markdown(improved)
            errs = [x.message[:140] for x in rv.issues if x.severity == "error"]
            sc_i = spec_check.check_spec(spec, swc, module.runnables)
            line += (f" | improved: approved={rv.approved} coverage={rv.coverage_pct}% errors={rv.error_count} "
                     f"warnings={rv.warning_count} gaps={spec_check.gap_count(sc_i)} usable={len(sc_i['usable'])}")
            line += "".join(f"\n      error: {e}" for e in errs[:3])
        elif do_review:
            rv = aio.run_sync(design.review_spec(module, text, spec))
            errs = [x.message[:140] for x in rv.issues if x.severity == "error"]
            line += f" | review approved={rv.approved} coverage={rv.coverage_pct}% errors={rv.error_count}"
            line += "".join(f"\n      error: {e}" for e in errs[:3])
        print(f"{line}  ({time.time() - t0:.0f}s)", flush=True)
        out = ROOT / "outputs" / "_loops" / "spec_only"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{swc}_{time.strftime('%H%M%S')}_{i}.md").write_text(spec, encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
