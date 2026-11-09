"""Run ordering/archive, job cancel + live stages, multi-SWC chain, honest verdicts, compile quality gate."""

import asyncio
import json
import threading
import time
from types import SimpleNamespace

import pytest

from mudmut_core import chain, compilable, jobs, report, results
from mudmut_core.workspace import LATEST, Run


# ── run list order + archive ────────────────────────────────────────────────
def _run(root, name, created):
    d = root / name
    d.mkdir(parents=True)
    (d / "state.json").write_text(json.dumps({"swc": name, "preset": "p", "created": created}))
    return d


def test_runs_sorted_by_creation_not_name(tmp_path):
    _run(tmp_path, "eps", "20260101_000000")                       # agent run, free-form name, old
    _run(tmp_path, "20260105_120000_SWC_A_custom", "20260105_120000")
    names = [r.folder.name for r in Run.list_runs(root=tmp_path)]
    assert names == ["20260105_120000_SWC_A_custom", "eps"]


def test_archive_and_restore(tmp_path):
    old = _run(tmp_path, "20260101_000000_SWC_A_custom", "20260101_000000")
    new = _run(tmp_path, "20260102_000000_SWC_B_custom", "20260102_000000")
    (tmp_path / LATEST).write_text(new.name)
    target = Run.load(new).archive()
    assert not new.exists() and target.is_dir()
    assert (tmp_path / LATEST).read_text() == old.name
    assert [r.folder.name for r in Run.list_archived(root=tmp_path)] == [new.name]
    Run.restore_archived(new.name, root=tmp_path)
    assert new.is_dir() and not Run.list_archived(root=tmp_path)
    assert [r.folder.name for r in Run.list_runs(root=tmp_path)][0] == new.name


# ── jobs: cancel and live stage state ───────────────────────────────────────
def _wait(job):
    for _ in range(200):
        if not job.running:
            return
        time.sleep(0.01)


def test_cancel_stops_job_and_marks_cancelled():
    gate = threading.Event()

    def work(progress):
        progress({"stage": "import", "message": "ok", "done": True})
        gate.wait(2)
        if progress.cancelled():
            raise chain.ChainCancelled("Cancelled before stage 'plan'")
        return "finished"

    job = jobs.start("q-cancel", work, quick=True)
    time.sleep(0.05)
    assert job.stage_state("import") == "done" and job.stage_state("plan") == "running"
    assert jobs.request_cancel(job.id)
    gate.set()
    _wait(job)
    assert job.status == "cancelled" and "plan" in job.error
    assert not jobs.request_cancel(job.id)          # not running any more


def test_new_run_folder_restarts_the_live_rail():
    def work(progress):
        progress({"stage": "spec", "message": "a", "done": True, "run_folder": "/x/run1"})
        progress({"stage": "workspace", "message": "b", "run_folder": "/x/run2"})
        return 1

    job = jobs.start("q-rail", work, quick=True, track=False)
    _wait(job)
    assert job.run_folder == "/x/run2" and "spec" not in job.stages_done


def test_clear_finished_and_any_running():
    job = jobs.start("q-done", lambda p: 1, track=False)
    _wait(job)
    assert not jobs.any_running()
    assert jobs.clear_finished() >= 1 and jobs.get(job.id) is None


# ── chain helpers ────────────────────────────────────────────────────────────
def _req(rid, asil=None):
    return SimpleNamespace(req_id=rid, safety_level=SimpleNamespace(value=asil) if asil else None)


class _Set:
    def __init__(self, items):
        self.requirements = items

    @property
    def count(self):
        return len(self.requirements)

    def model_copy(self, update):
        return _Set(update["requirements"])


def test_requirements_for_module_and_asil():
    reqs = _Set([_req("REQ-1", "QM"), _req("REQ-2", "ASIL-D"), _req("REQ-3", "ASIL-B")])
    mod = SimpleNamespace(req_ids=["REQ-1", "REQ-3"])
    only = chain.requirements_for_module(reqs, mod)
    assert [r.req_id for r in only.requirements] == ["REQ-1", "REQ-3"]
    assert chain.requirements_for_module(reqs, SimpleNamespace(req_ids=[])) is reqs      # no IDs: all
    assert chain.requirements_for_module(reqs, SimpleNamespace(req_ids=["X"])) is reqs   # no match: all
    assert chain.highest_asil(reqs) == "ASIL-D" and chain.highest_asil(only) == "ASIL-B"


def test_check_cancel():
    chain._check_cancel(None, "spec")
    chain._check_cancel(lambda: False, "spec")
    with pytest.raises(chain.ChainCancelled):
        chain._check_cancel(lambda: True, "spec")


def test_run_all_swcs_runs_every_planned_component(monkeypatch):
    plan = SimpleNamespace(modules=[SimpleNamespace(swc_name=n, req_ids=[]) for n in ("SWC_A", "SWC_B", "SWC_C")])
    monkeypatch.setattr(chain, "_import", lambda f: _Set([_req("REQ-1")]))

    async def fake_plan(text):
        return plan
    monkeypatch.setattr(chain.design, "plan_modules", fake_plan)
    monkeypatch.setattr(chain.design, "requirements_text", lambda r: "text")
    calls = []

    async def fake_chain(req, *, swc, prepared, progress, **kw):
        calls.append(swc)
        assert prepared[1] is plan                       # one shared plan
        progress({"stage": "spec", "message": "spec done", "done": True})
        if swc == "SWC_B":
            raise RuntimeError("model down")
        return {"run_folder": f"/runs/{swc}"}
    monkeypatch.setattr(chain, "run_full_chain", fake_chain)
    events = []
    out = asyncio.run(chain.run_all_swcs("f.csv", progress=events.append))
    assert calls == ["SWC_A", "SWC_B", "SWC_C"]
    assert [r["status"] for r in out["swcs"]] == ["done", "error", "done"]
    assert out["run_folder"] == "/runs/SWC_C" and "SWC_B" in out["warnings"][0]
    fractions = [e["fraction"] for e in events if "fraction" in e]
    assert fractions == sorted(fractions) and fractions[-1] <= 1.0
    only = asyncio.run(chain.run_all_swcs("f.csv", only=["SWC_C"]))
    assert [r["swc"] for r in only["swcs"]] == ["SWC_C"]


# ── honest verdicts ─────────────────────────────────────────────────────────
def _verdicts(tmp_path, **summary):
    run = Run.create("SWC_T", preset="p", root=tmp_path)
    base = {"swc": "SWC_T", "quick": True, "tests_generated": 1, "generation_failed": 0,
            "compilability": {"compile_ok": True, "stubbed": 0, "kept": 5},
            "tests": {"status": "passed", "junit": {"passed": 1}}, "trace": {}}
    base.update(summary)
    report.write_run_report(run, base)
    return json.loads((run.folder / "run.json").read_text(encoding="utf-8"))


def test_smoke_test_only_is_a_failure(tmp_path):
    data = _verdicts(tmp_path, tests={"status": "passed", "junit": {"passed": 1}, "smoke_fallback": True,
                                      "quarantined_tests": ["Test_RE_X.cpp"]})
    assert data["verdicts"]["build_run"] == "❌" and data["verdicts"]["generate_tests"] == "❌"
    assert any("No AI-written test compiled" in n for n in data["quality_notes"])


def test_dropped_logic_fails_compilable(tmp_path):
    data = _verdicts(tmp_path, compilability={"compile_ok": True, "stubbed": 2, "kept": 5, "logic_stubbed": 1,
                                              "never_assigned": ["l_f32Cmd"], "uninitialized_uses": 1})
    assert data["verdicts"]["compilable"] == "❌"
    assert any("l_f32Cmd" in n for n in data["quality_notes"])
    ok = _verdicts(tmp_path, compilability={"compile_ok": True, "stubbed": 2, "kept": 5})
    assert ok["verdicts"]["compilable"] == "⚠️"                  # only prose labels stubbed


def test_asil_d_flagged_for_review(tmp_path):
    data = _verdicts(tmp_path, max_asil="ASIL-D")
    assert any("ASIL-D" in n and "review" in n for n in data["quality_notes"])
    assert not any("ASIL" in n for n in _verdicts(tmp_path, max_asil="QM")["quality_notes"])


# ── compile quality gate ─────────────────────────────────────────────────────
def test_logic_statement_classification():
    assert compilable.is_logic_statement("    l_f32Target = irvBrakeDemand * K_mass;")
    assert compilable.is_logic_statement("    ApplyRamp(a, b);")
    assert not compilable.is_logic_statement("    Guard;")
    assert not compilable.is_logic_statement("    Compute;  /* Compute */")


def test_unassigned_reads_finds_dropped_computation():
    code = """
float32 l_f32Cmd;
float32 l_f32Target;
float32 l_f32Fb;
float32 l_k = 2.0f;
void RE_X(void)
{
    /* TODO(design): l_f32Target = demand * K_gain; */
    Rte_Read_RP_Fb(&l_f32Fb);
    l_f32Cmd++;
    Rte_Write_PP_Out(clamp(l_f32Target + l_f32Fb + l_k, 0, 10));
}
"""
    assert compilable.unassigned_reads(code) == ["l_f32Target"]


def test_comment_line_has_no_nested_comment():
    out = compilable._comment_line("    Guard;  /* Guard */")
    assert out.count("/*") == 1 and out.count("*/") == 1


def test_coverage_for_target_file_only(tmp_path):
    info = tmp_path / "coverage.info"
    info.write_text("SF:/r/03_mut/SWC_A.c\nLF:15\nLH:8\nBRF:6\nBRH:3\nend_of_record\n"
                    "SF:/r/03_mut/Test_Smoke.cpp\nLF:10\nLH:10\nend_of_record\n")
    target = results.coverage_summary(info, only="SWC_A.c")
    assert target["files"] == 1 and target["line_pct"] == 53.3 and target["branch_pct"] == 50.0
    assert results.coverage_summary(info)["line_pct"] == 72.0
    assert results.coverage_summary(info, only="Other.c")["files"] == 0


def test_effective_verdicts_apply_new_rules_to_old_runs():
    old = {"verdicts": {"generate_tests": "✅", "build_run": "⚠️", "compilable": "⚠️", "trace": "✅"},
           "tests": {"smoke_fallback": True}, "compilability": {"logic_stubbed": 2}}
    v = report.effective_verdicts(old)
    assert v["build_run"] == "❌" and v["generate_tests"] == "❌" and v["compilable"] == "❌" and v["trace"] == "✅"
    assert report.effective_verdicts({"verdicts": {"build_run": "✅"}, "tests": {}})["build_run"] == "✅"
