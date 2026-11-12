#!/usr/bin/env python3
"""No-LLM check: regenerate the Rte stubs of a finished run with the current compilable.py, rebuild and run its
existing tests, print the scorecard. Used to verify stub/codegen fixes without API cost.

    python agentic/loop/rebuild_stubs.py <source_run_folder> <new_name>
"""
import json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from mudmut_core import env, compilable, verify  # noqa: E402
env.ensure_environment()
import scorecard  # noqa: E402

src, name = Path(sys.argv[1]), sys.argv[2]
dst = ROOT / "outputs" / name
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst, ignore=shutil.ignore_patterns("quarantined"))
swc = [p.stem for p in (dst / "02_code").glob("SWC_*.c")][0]
code = (dst / "02_code" / f"{swc}.c").read_text(encoding="utf-8")
spec = dst / "01_mud" / "mud_spec.md"
rep = compilable.make_compilable(code, swc, dst / "02_code", spec_md=spec.read_text(encoding="utf-8") if spec.exists() else None)
print("compile_ok", rep.compile_ok, "kept", rep.kept_statements, "stubbed", rep.stubbed_statements)
mut = dst / "03_mut"
for f in (dst / "02_code").glob("Rte_*"):
    shutil.copy2(f, mut / f.name)
shutil.copy2(dst / "02_code" / f"{swc}.c", mut / f"{swc}.c")
result = verify.build_and_run(mut)
print("status", result.get("status"), result.get("junit"))
rj = json.loads((dst / "run.json").read_text(encoding="utf-8"))
rj["tests"] = {"status": result.get("status"), "junit": result.get("junit"), "quarantined_tests": []}
(dst / "run.json").write_text(json.dumps(rj, indent=2), encoding="utf-8")
print(scorecard.render(scorecard.scorecard(dst)))
