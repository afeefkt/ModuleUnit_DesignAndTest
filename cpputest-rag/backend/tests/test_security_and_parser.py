"""Regression tests for path confinement, the origin guard and the C parser.

Run from cpputest-rag/backend:  python -m pytest -q tests
(No Ollama or Docker needed — startup events are not triggered.)
"""

import asyncio
import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import database
from app.config import config
from app.main import app
from app.services.c_parser import analyze_c_file_simple
from app.services.test_generator import _unique_test_groups


@pytest.fixture()
def dirs(tmp_path, monkeypatch):
    projects = tmp_path / "c_projects"
    outputs = tmp_path / "generated_tests"
    (projects / "SWC_Demo").mkdir(parents=True)
    (projects / "SWC_Demo" / "demo.c").write_text("int add(int a, int b) { return a + b; }\n")
    run = outputs / "tests_20260101_000000_abc123"
    (run / "coverage_html").mkdir(parents=True)
    (run / "coverage_html" / "index.html").write_text("<html>cov</html>")
    (tmp_path / "secret.txt").write_text("top secret")
    monkeypatch.setattr(config, "C_PROJECT_DIR", projects)
    monkeypatch.setattr(config, "OUTPUT_DIR", outputs)
    # Startup events don't run under TestClient(app) — init a throwaway DB so
    # get_db() doesn't connect to str(None) and create a file named "None".
    asyncio.run(database.init_db(tmp_path / "test.db"))
    return tmp_path


@pytest.fixture()
def client():
    return TestClient(app)


# ── path confinement ────────────────────────────────────────────────────────

def test_coverage_html_serves_file_inside_run(dirs, client):
    r = client.get("/coverage-html/tests_20260101_000000_abc123/index.html")
    assert r.status_code == 200 and "cov" in r.text


@pytest.mark.parametrize("path", ["../../../secret.txt", "..%2F..%2F..%2Fsecret.txt"])
def test_coverage_html_rejects_traversal(dirs, client, path):
    r = client.get(f"/coverage-html/tests_20260101_000000_abc123/{path}")
    assert r.status_code in (403, 404)
    assert "top secret" not in r.text


@pytest.mark.parametrize("name", ["x;touch pwned;#", "a b", "..", "$(id)"])
def test_run_tests_rejects_unsafe_directory_names(dirs, client, name):
    r = client.post("/run-tests", params={"test_directory": name})
    assert r.status_code in (400, 404)


def test_analyze_rejects_path_outside_projects(dirs, client):
    r = client.get("/analyze-project", params={"project_path": str(dirs)})
    assert r.status_code in (403, 404)


def test_upload_rejects_zip_slip(dirs, client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../../escaped.c", "int x;")
    r = client.post(
        "/upload-project",
        files={"file": ("evil.zip", buf.getvalue(), "application/zip")},
    )
    assert r.status_code == 400
    assert not (dirs / "escaped.c").exists()


def test_upload_rejects_traversal_in_filename(dirs, client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.c", "int x;")
    r = client.post(
        "/upload-project",
        files={"file": ("..\\..\\evil name.zip", buf.getvalue(), "application/zip")},
    )
    assert r.status_code == 400


# ── origin guard ────────────────────────────────────────────────────────────

def test_cross_site_post_is_rejected(dirs, client):
    r = client.post(
        "/run-tests",
        params={"test_directory": "tests_20260101_000000_abc123"},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403


def test_post_without_origin_reaches_handler(dirs, client):
    # bridge / curl send no Origin; the unknown dir then yields 404, not 403
    r = client.post("/run-tests", params={"test_directory": "tests_missing"})
    assert r.status_code == 404


# ── parser ──────────────────────────────────────────────────────────────────

def test_parser_handles_pointers_static_and_keeps_trace_comments(tmp_path):
    src = tmp_path / "m.c"
    src.write_text(
        "/* header\n   comment */\n"
        "static int helper(int a) { return a; }\n"
        "char *dup_str(const char *s, size_t n)\n"
        "{\n"
        '    const char *m = "{";\n'
        "    if (s && n) { return 0; } /* [REQ-X-001] */\n"
        "    return 0;\n"
        "}\n"
    )
    fns = {f.name: f for f in analyze_c_file_simple(src)}
    assert set(fns) == {"helper", "dup_str"}
    assert fns["helper"].is_static and fns["helper"].line_number == 3
    assert fns["dup_str"].return_type == "char *"
    assert fns["dup_str"].parameters[0] == {"type": "const char *", "name": "s"}
    assert fns["dup_str"].line_number == 4
    assert "[REQ-X-001]" in fns["dup_str"].source_code


def test_test_group_names_are_scoped_to_function():
    code = "TEST_GROUP(Math){};\nTEST(Math, adds){}\n"
    out = _unique_test_groups(code, "add")
    assert "TEST_GROUP(add_Math)" in out and "TEST(add_Math, adds)" in out
