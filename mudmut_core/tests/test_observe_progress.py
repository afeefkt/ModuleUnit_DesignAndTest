"""AI monitor (observer), streaming parser, progress percent model and background jobs."""

import json
import time

import pytest

from mudmut_core import jobs, progress
from mudmut_core.llm import client, observe, providers


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(observe, "STATE_LOG", tmp_path / "state_llm_log.jsonl")
    monkeypatch.setattr(progress, "TIMINGS_FILE", tmp_path / "timings.json")
    observe.clear()
    yield
    observe.clear()


# ── observer ────────────────────────────────────────────────────────────────
def test_start_chunk_end_records_a_call_and_persists(tmp_path):
    run = tmp_path / "run1"
    with observe.context(run=run, stage="spec"):
        cid = observe.start_call(provider="ollama", model="qwen3", kind="stream", system="sys", user="usr")
        observe.add_chunk(cid, reasoning="hmm ")
        observe.add_chunk(cid, text="Hello")
        observe.end_call(cid, input_tokens=5, output_tokens=2, latency_ms=1000)
    call = observe.recent()[0]
    assert call["stage"] == "spec" and call["status"] == "done"
    assert call["response"] == "Hello" and call["thinking"] == "hmm "
    assert call["first_token_ms"] is not None and call["tokens_per_s"] == 2.0
    line = json.loads((run / "llm_log.jsonl").read_text().splitlines()[0])
    assert line["model"] == "qwen3" and line["user"] == "usr"


def test_empty_and_error_calls_are_flagged():
    a = observe.start_call(provider="p", model="m", kind="chat")
    observe.end_call(a, content="   ")
    b = observe.start_call(provider="p", model="m", kind="chat")
    observe.error_call(b, "ProviderError: 429")
    status = {c["id"]: c["status"] for c in observe.recent()}
    assert status[a] == "empty" and status[b] == "error"
    assert observe.summary()["—"]["errors"] == 1 and observe.summary()["—"]["empty"] == 1


def test_secrets_never_recorded_and_text_is_truncated(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-SECRET-VALUE-123456")
    cid = observe.start_call(provider="p", model="m", kind="chat",
                             user="key is sk-or-SECRET-VALUE-123456 ok " + "x" * (observe.MAX_TEXT + 50))
    call = observe.recent()[0]
    assert "SECRET-VALUE" not in json.dumps(call) and "***" in call["user"]
    assert len(call["user"]) < observe.MAX_TEXT + 100 and "truncated" in call["user"]
    assert cid


def test_mud_tool_events_map_to_calls_with_provider():
    observe.handle_event("start", {"call_id": 7, "base_url": "http://localhost:11434/v1",
                                   "model": "qwen3:8b", "system": "s", "user": "u", "kind": "generate"})
    observe.handle_event("end", {"call_id": 7, "content": "done", "reasoning": "why", "input_tokens": 3,
                                 "output_tokens": 4, "finish_reason": "stop", "latency_ms": 2000})
    call = observe.recent()[0]
    assert call["id"] == "m7" and call["provider"] == "ollama"
    assert call["thinking"] == "why" and call["output_tokens"] == 4


def test_ring_buffer_is_bounded():
    for _ in range(observe.MAX_CALLS + 20):
        observe.start_call(provider="p", model="m", kind="chat")
    assert len(observe.recent(limit=10_000)) == observe.MAX_CALLS


# ── streaming parser ─────────────────────────────────────────────────────────
def _sse(*deltas):
    return [f"data: {json.dumps({'choices': [{'delta': d}]})}" for d in deltas] + ["data: [DONE]"]


def test_sse_separates_reasoning_field_from_content():
    parts = list(client.iter_sse_deltas(iter(_sse({"reasoning": "think"}, {"content": "Hi"}))))
    assert parts == [("reasoning", "think"), ("text", "Hi")]


def test_sse_handles_inline_think_tags_across_chunks():
    parts = list(client.iter_sse_deltas(iter(_sse({"content": "a<think>x"}, {"content": "y</think>b"}))))
    assert parts == [("text", "a"), ("reasoning", "x"), ("reasoning", "y"), ("text", "b")]


# ── progress model ───────────────────────────────────────────────────────────
def test_weights_cover_all_stages_and_percent_is_capped_until_complete():
    for quick in (True, False):
        t = progress.ProgressTracker(quick=quick, timings={})
        assert ("review" in t.stages) == (not quick)
        last = -1
        for stage in list(t.stages):
            t.update({"stage": stage, "message": "x", "done": True})
            assert last <= t.percent <= 99
            last = t.percent
        assert t.percent == 99 or t.current is None
        t.complete()
        assert t.percent == 100


def test_fraction_inside_a_stage_moves_the_bar():
    t = progress.ProgressTracker(quick=True, timings={})
    for s in ("import", "plan", "spec", "activity", "compilable"):
        t.update({"stage": s, "message": "", "done": True})
    before = t.percent
    t.update({"stage": "generate_tests", "message": "", "fraction": 0.5})
    assert t.percent > before


def test_timings_moving_average_changes_expected_durations():
    progress.record_timings({"spec": 100.0}, quick=True)
    progress.record_timings({"spec": 200.0}, quick=True)
    assert progress.load_timings()["quick:spec"] == pytest.approx(130.0)
    assert progress.expected_seconds(True)["spec"] == pytest.approx(130.0)


# ── jobs ─────────────────────────────────────────────────────────────────────
def test_job_runs_in_background_and_reports_progress():
    def work(report):
        report({"stage": "import", "message": "imported", "done": True})
        time.sleep(0.05)
        return {"ok": True}

    job = jobs.start("test-job-1", work, quick=True)
    for _ in range(100):
        if not job.running:
            break
        time.sleep(0.02)
    assert job.status == "done" and job.result == {"ok": True} and job.percent == 100
    assert any("imported" in line for line in job.log)


def test_job_error_is_captured_not_raised():
    def boom(report):
        raise RuntimeError("model down")

    job = jobs.start("test-job-2", boom, track=False)
    for _ in range(100):
        if not job.running:
            break
        time.sleep(0.02)
    assert job.status == "error" and "model down" in job.error


def test_same_label_does_not_start_twice():
    import threading
    gate = threading.Event()
    first = jobs.start("test-job-3", lambda report: gate.wait(2), track=False)
    second = jobs.start("test-job-3", lambda report: None, track=False)
    assert first is second
    gate.set()


def test_orphan_calls_are_adopted_by_the_run(tmp_path):
    cid = observe.start_call(provider="p", model="m", kind="chat", stage="plan")
    observe.end_call(cid, content="plan result")
    run = tmp_path / "run9"
    assert observe.adopt_orphans(run) == 1
    assert observe.recent(run=str(run))[0]["stage"] == "plan"
    assert "plan result" in (run / "llm_log.jsonl").read_text()
