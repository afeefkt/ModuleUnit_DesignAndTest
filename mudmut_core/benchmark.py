"""Benchmark tables from the run folders in ``outputs/`` (the numbers in ``BENCHMARK.md``).

    python -m mudmut_core.benchmark                    # print the tables
    python -m mudmut_core.benchmark --write BENCHMARK.md   # replace the generated part of the file

Every number comes from a run folder (``run.json``, ``02_code/compilability.json``,
``04_trace/trace.json``, ``03_mut/``) and is printed next to that folder's name. Nothing is
estimated. The ``run.json`` written when the run finished is the source for test results; a
later manual rebuild that changed ``03_mut/results.json`` is flagged, not merged.

It also counts **no-op test files**: generated test files in which every test case asserts only a
constant (``CHECK(true)``, ``CHECK_TRUE(1)`` …). The trace counts such a file as verification when
it passes, so the verified count is split into "backed by a real assertion" and "no-op only".
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Optional

from mudmut_core.env import REPO_ROOT
from mudmut_core.report import STAGE_ORDER, effective_verdicts
from mudmut_core.workspace import RUNS_ROOT, Run

BEGIN = "<!-- BEGIN GENERATED: python -m mudmut_core.benchmark --write BENCHMARK.md -->"
END = "<!-- END GENERATED -->"

# ── no-op test detection ──────────────────────────────────────────────────────
_TEST_RE = re.compile(r"^\s*TEST\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)", re.MULTILINE)
_ASSERT_RE = re.compile(
    r"\b(CHECK|CHECK_TRUE|CHECK_FALSE|CHECK_TEXT|CHECK_TRUE_TEXT|CHECK_FALSE_TEXT|CHECK_EQUAL\w*|CHECK_COMPARE\w*|"
    r"CHECK_THROWS|LONGS_EQUAL\w*|UNSIGNED_LONGS_EQUAL\w*|LONGLONGS_EQUAL\w*|UNSIGNED_LONGLONGS_EQUAL\w*|"
    r"DOUBLES_EQUAL\w*|STRCMP\w*|STRNCMP\w*|POINTERS_EQUAL\w*|FUNCTIONPOINTERS_EQUAL\w*|BYTES_EQUAL\w*|"
    r"SIGNED_BYTES_EQUAL\w*|MEMCMP_EQUAL\w*|BITS_EQUAL\w*|ENUMS_EQUAL\w*|FAIL\w*)\s*\(")
_CONST_TRUE = {"true", "1", "TRUE"}
_CONST_FALSE = {"false", "0", "FALSE"}


def _call_args(text: str, start: int) -> str:
    """The argument text of the call whose ``(`` is at ``start`` (balanced parentheses)."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
    return text[start + 1:]


def _is_noop_assertion(macro: str, args: str) -> bool:
    first = args.split(",")[0].strip()
    if macro in ("CHECK", "CHECK_TRUE", "CHECK_TEXT", "CHECK_TRUE_TEXT"):
        return first in _CONST_TRUE
    if macro in ("CHECK_FALSE", "CHECK_FALSE_TEXT"):
        return first in _CONST_FALSE
    return False


def test_case_kinds(source: str) -> dict[str, bool]:
    """``{test name: has a real assertion}`` for each ``TEST(group, name)`` in a CppUTest file.

    A real assertion compares something the code computed (``LONGS_EQUAL``, ``CHECK(x == 3)`` …),
    or sets a mock expectation. ``CHECK(true)`` and friends are not real assertions.
    """
    heads = list(_TEST_RE.finditer(source))
    kinds: dict[str, bool] = {}
    for i, head in enumerate(heads):
        body = source[head.end(): heads[i + 1].start() if i + 1 < len(heads) else len(source)]
        real = "mock()" in body and ".expect" in body
        for m in _ASSERT_RE.finditer(body):
            if not _is_noop_assertion(m.group(1), _call_args(body, m.end() - 1)):
                real = True
                break
        kinds[head.group(2)] = real
    return kinds


def noop_test_files(test_dir: Path, names: list[str]) -> list[str]:
    """Test files (of ``names`` in ``test_dir``) with test cases, none of which has a real assertion."""
    out = []
    for name in names:
        p = test_dir / name
        if not p.is_file():
            continue
        kinds = test_case_kinds(p.read_text(encoding="utf-8", errors="ignore"))
        if kinds and not any(kinds.values()):
            out.append(name)
    return out


# ── which requirement file a run used ─────────────────────────────────────────
_ID_SETS: Optional[dict[str, frozenset]] = None


def _input_id_sets() -> dict[str, frozenset]:
    """Requirement-ID set of every CSV/XLSX under ``inputs/requirements*/`` (imported once)."""
    global _ID_SETS
    if _ID_SETS is None:
        _ID_SETS = {}
        from mudmut_core import design
        skip = ("readme", "change_log", "test_design", "trace_matrix", "_extended", "polished")
        for base in sorted(REPO_ROOT.glob("inputs/requirements*")):
            for p in sorted(base.rglob("*")):
                if p.suffix.lower() not in (".csv", ".xlsx") or any(s in p.name.lower() for s in skip):
                    continue
                try:
                    ids = frozenset(r.req_id for r in design.import_requirements(p).requirement_set.requirements)
                except Exception:  # noqa: BLE001 - not a requirement file
                    continue
                if ids:
                    _ID_SETS[p.relative_to(REPO_ROOT / "inputs").as_posix()] = ids
    return _ID_SETS


def input_file_of(run: Run) -> tuple[str, int]:
    """``(file under inputs/ whose IDs equal the run's input, number of requirements)``."""
    data = run.read_json_in("input", "requirements.json")
    items = data.get("requirements") if isinstance(data, dict) else data
    ids = frozenset(r.get("req_id") for r in items or [] if isinstance(r, dict))
    if not ids:
        return "—", 0
    matches = [name for name, s in _input_id_sets().items() if s == ids]
    if not matches:
        return "not found under inputs/", len(ids)
    # The same IDs can be in a .csv and an .xlsx copy; prefer the CSV.
    return sorted(matches, key=lambda n: (not n.endswith(".csv"), n))[0], len(ids)


# ── one row per run ───────────────────────────────────────────────────────────
def _model(models: dict, stage: str) -> str:
    for group in (models or {}).values():
        cfg = (group or {}).get(stage)
        if cfg:
            return f"{cfg.get('provider', 'ollama')}/{cfg.get('model', '')}"
    return "—"


def run_row(run: Run) -> Optional[dict[str, Any]]:
    """The benchmark numbers of one run, or None for a folder without a run report."""
    data = run.read_json("run.json")
    if not isinstance(data, dict) or not data.get("verdicts"):
        return None
    comp = run.read_json_in("code", "compilability.json") or {}
    tests = data.get("tests") or {}
    junit = tests.get("junit") or {}
    results = run.read_json_in("mut", "results.json") or {}
    generation = results.get("generation") or {}
    trace = run.read_json_in("trace", "trace.json") or {}
    summary = trace.get("summary") or {}
    verdicts = effective_verdicts(data)
    source, n_reqs = input_file_of(run)

    generated = generation.get("tests_generated")
    quarantined = len(tests.get("quarantined_tests") or [])
    compiled = None if generated is None else (0 if tests.get("smoke_fallback") else max(generated - quarantined, 0))

    traced_files = (trace.get("generated_tests") or {}).get("test_files") or []
    noop = noop_test_files(run.dir("mut"), traced_files) if traced_files else []
    verified = [t for t in trace.get("trace") or [] if t.get("status") == "verified_by_test"]
    real_backed = [t for t in verified if any(f not in noop for f in t.get("verified_by") or [])]

    later = (results.get("run") or {}).get("junit")
    timings = {k: v for k, v in (data.get("timings") or {}).items() if isinstance(v, (int, float))}
    total = comp.get("total_statements")
    stubbed = comp.get("stubbed_statements")
    failed_stage = data.get("failed_stage")
    return {
        "run": run.folder.name,
        "date": run.created_key[:8],
        "input": source,
        "requirements": n_reqs,
        "swc": run.swc,
        "mode": {True: "quick", False: "full"}.get(run.state.get("quick"), "—"),
        "spec_model": _model(data.get("models"), "mud_spec_generator"),
        "test_model": _model(data.get("models"), "test_generator"),
        "cloud": ", ".join(data.get("cloud_providers") or []) or "no",
        "outcome": (f"failed at {failed_stage}: {str(data.get('error') or '').split(' for url')[0][:70]}"
                    if failed_stage else "finished"),
        "verdicts": "".join(verdicts.get(k, "·") for k in STAGE_ORDER),
        "statements": f"{comp.get('kept_statements')} / {total}" if total else "—",
        "stubbed_pct": round(100 * stubbed / total) if total and stubbed is not None else None,
        "logic_stubbed": comp.get("logic_stubbed"),
        "never_assigned": len(comp["never_assigned"]) if "never_assigned" in comp else None,   # older runs: not recorded
        "tests_generated": generated,
        "tests_compiled": compiled,
        "tests_quarantined": quarantined if generated is not None else None,
        "passed": junit.get("passed"),
        "failed": (junit.get("failures") or 0) + (junit.get("errors") or 0) if junit else None,
        "test_source": "smoke" if tests.get("smoke_fallback") else ("AI" if junit else "—"),
        "traced": summary.get("requirements"),
        "verified": summary.get("verified_by_test"),
        "verified_real": len(real_backed) if summary else None,
        "failing": summary.get("failing_test"),
        "not_verified": summary.get("not_verified"),
        "noop_files": noop,
        "minutes": round(sum(timings.values()) / 60, 1) if timings else None,
        "later_rebuild": bool(later) and later != junit,
    }


def collect(root: Optional[Path] = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Rows for every run with a report (oldest first) and the folders left out, with the reason."""
    base = root or RUNS_ROOT
    rows, skipped = [], []
    for run in sorted(Run.list_runs(root=base), key=lambda r: (r.created_key, r.folder.name)):
        row = run_row(run)
        if row is None:
            skipped.append(f"`{run.folder.name}` — no run report (`run.json` without verdicts)")
        else:
            rows.append(row)
    for d in sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []:
        if not (d / "state.json").is_file() and not d.name.startswith("_"):
            skipped.append(f"`{d.name}/` — not a pipeline run folder")
    return rows, skipped


# ── markdown ──────────────────────────────────────────────────────────────────
def _v(value: Any) -> str:
    return "—" if value is None or value == "" else str(value)


def markdown(rows: list[dict[str, Any]], skipped: list[str]) -> str:
    out = [BEGIN, "",
           f"_{len(rows)} run(s) with a report in `outputs/`, oldest first. Stage letters: "
           "import · plan · spec · review · activity · compilable · tests · build & run · trace "
           "(✅ pass, ⚠️ partial, ❌ failed, — not run). In the number columns — means not recorded "
           "(older runs) or not reached (failed runs)._", "",
           "### Runs", "",
           "| Run folder | Input (under `inputs/`) | Reqs | Mode | Spec / test model | Data to cloud | Outcome | Stages |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| `{r['run']}` | `{r['input']}` | {r['requirements']} | {r['mode']} | "
                   f"`{r['spec_model']}` / `{r['test_model']}` | {r['cloud']} | {r['outcome']} | {r['verdicts']} |")
    out += ["", "### Design and C code", "",
            "| Run folder | Statements kept / total | Stubbed % | Design logic commented out | Read but never assigned | Minutes |",
            "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| `{r['run']}` | {r['statements']} | {_v(r['stubbed_pct'])} | {_v(r['logic_stubbed'])} | "
                   f"{_v(r['never_assigned'])} | {_v(r['minutes'])} |")
    out += ["", "### Tests and traceability", "",
            "| Run folder | AI test files generated / compiled / quarantined | Tests passed / failed | Results from | "
            "Reqs in trace | `verified_by_test` | of which backed by a real assertion | failing | not verified | No-op test files |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        files = f"{_v(r['tests_generated'])} / {_v(r['tests_compiled'])} / {_v(r['tests_quarantined'])}"
        tests = f"{_v(r['passed'])} / {_v(r['failed'])}" + (" ¹" if r["later_rebuild"] else "")
        noop = ", ".join(f"`{n}`" for n in r["noop_files"]) or "—"
        out.append(f"| `{r['run']}` | {files} | {tests} | {r['test_source']} | {_v(r['traced'])} | {_v(r['verified'])} | "
                   f"{_v(r['verified_real'])} | {_v(r['failing'])} | {_v(r['not_verified'])} | {noop} |")
    if any(r["later_rebuild"] for r in rows):
        out += ["", "¹ `03_mut/results.json` holds a later manual rebuild with other numbers; the table shows the "
                    "results recorded when the run finished (`run.json`)."]
    if skipped:
        out += ["", "Not counted:", ""] + [f"- {s}" for s in skipped]
    out += ["", END]
    return "\n".join(out)


def write(path: Path, root: Optional[Path] = None) -> None:
    """Replace the generated block of ``path`` (between the markers) with fresh tables."""
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{path} has no generated block ({BEGIN!r} … {END!r})")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    path.write_text(head + markdown(*collect(root)) + tail, encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", type=Path, help="Markdown file whose generated block is replaced")
    ap.add_argument("--outputs", type=Path, default=None, help="Runs folder (default: outputs/)")
    args = ap.parse_args(argv)
    if args.write:
        write(args.write, args.outputs)
        print(f"updated {args.write}")
    else:
        print(markdown(*collect(args.outputs)))


if __name__ == "__main__":
    main()
