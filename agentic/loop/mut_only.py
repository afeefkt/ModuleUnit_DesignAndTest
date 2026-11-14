#!/usr/bin/env python3
"""MUT-only inner loop: copy a finished run's MUD+code, regenerate tests, build/run, print the scorecard.

    python agentic/loop/mut_only.py <source_run_folder> <new_name> [--no-generate]

Used to iterate on step 5/6 (tests, coverage) without paying for MUD again. Uses the deepseek preset.
"""
from __future__ import annotations
import json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from mudmut_core import env, agents, aio, verify  # noqa: E402
env.ensure_environment()
import scorecard  # noqa: E402


def main(argv):
    src, name = Path(argv[0]), argv[1]
    dst = ROOT / "outputs" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("03_mut", "04_trace", "quarantined"))
    (dst / "03_mut").mkdir()
    agents.apply_preset_with_report("deepseek")
    code_dir, mut_dir = dst / "02_code", dst / "03_mut"
    # Regenerate headers + stubs with the CURRENT compilable.py (the copied ones are from the source run's
    # version, so a stub/test-interface change would otherwise never reach the new tests).
    from mudmut_core import compilable
    swc = next(p.stem for p in code_dir.glob("SWC_*.c"))
    spec = dst / "01_mud" / "mud_spec.md"
    rep = compilable.make_compilable((code_dir / f"{swc}.c").read_text(encoding="utf-8"), swc, code_dir,
                                     spec_md=spec.read_text(encoding="utf-8") if spec.exists() else None)
    print(f"stubs regenerated: compile_ok={rep.compile_ok} kept={rep.kept_statements} stubbed={rep.stubbed_statements}")
    gen = aio.run_sync(verify.generate_tests(code_dir, output_dir=mut_dir))
    (mut_dir / "generation.json").write_text(json.dumps(gen, indent=2, default=str), encoding="utf-8")
    result = verify.fix_loop(mut_dir, max_attempts=verify.MAX_FIX_ATTEMPTS)
    (mut_dir / "results.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    rj = json.loads((dst / "run.json").read_text(encoding="utf-8"))
    rj["tests"] = {"status": result.get("status"), "junit": result.get("junit"),
                   "quarantined_tests": result.get("quarantined_tests", []),
                   "coverage_extended": result.get("coverage_extended", [])}
    (dst / "run.json").write_text(json.dumps(rj, indent=2), encoding="utf-8")
    print("coverage_extended:", result.get("coverage_extended"))
    print(scorecard.render(scorecard.scorecard(dst)))


if __name__ == "__main__":
    main(sys.argv[1:])
