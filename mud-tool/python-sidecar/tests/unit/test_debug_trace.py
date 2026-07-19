import json
from types import SimpleNamespace

from mudtool.debug_trace import RunDebugTrace


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_run_debug_trace_recreates_latest_file_each_run(tmp_path):
    settings = SimpleNamespace(project_root=tmp_path)

    first = RunDebugTrace(settings, "first_run", {"api_key": "secret-value"})
    first.record("step", message="old")
    assert len(_read_jsonl(first.path)) == 2

    second = RunDebugTrace(settings, "second_run", {"swc_name": "SWC_Test"})
    second.record("step", message="new")
    lines = _read_jsonl(second.path)

    assert first.path == second.path
    assert len(lines) == 2
    assert lines[0]["run_type"] == "second_run"
    assert lines[1]["data"]["message"] == "new"
    assert "old" not in second.path.read_text(encoding="utf-8")


def test_run_debug_trace_summarizes_large_payloads_and_redacts_secrets(tmp_path):
    settings = SimpleNamespace(project_root=tmp_path)
    trace = RunDebugTrace(settings, "review", {"api_key": "secret-value"})

    trace.record_event(
        "complete",
        {
            "stage": "done",
            "mud_spec_markdown": "A" * 3000,
            "authorization": "Bearer should-not-leak",
        },
    )

    lines = _read_jsonl(trace.path)
    assert lines[0]["data"]["metadata"]["api_key"] == "[redacted]"
    event = lines[1]["data"]["event"]
    assert event["mud_spec_markdown"]["omitted"] is True
    assert event["mud_spec_markdown"]["length"] == 3000
    assert event["authorization"] == "[redacted]"
