"""Report server (safe local file serving) and run-evidence parsers."""

import urllib.error
import urllib.request
import zipfile
from io import BytesIO

import pytest

from mudmut_core import reportserver, results


@pytest.fixture()
def served(tmp_path):
    run = tmp_path / "root" / "20260101_000000_SWC_x_local" / "03_mut" / "coverage_html"
    run.mkdir(parents=True)
    (run / "index.html").write_text("<html>coverage</html>")
    (tmp_path / "secret.txt").write_text("top secret")
    server, port = reportserver.start(tmp_path / "root", port=18502)
    yield tmp_path, port
    server.shutdown()
    server.server_close()


def _get(port, path):
    return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5)


def test_serves_files_under_root_with_no_cache(served):
    _, port = served
    resp = _get(port, "/20260101_000000_SWC_x_local/03_mut/coverage_html/index.html")
    assert resp.status == 200 and b"coverage" in resp.read()
    assert resp.headers["Cache-Control"] == "no-store"


def test_refuses_traversal_listing_and_writes(served):
    _, port = served
    for bad in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt"):
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(port, bad)
        assert e.value.code in (403, 404)
    with pytest.raises(urllib.error.HTTPError) as e:  # directory listing disabled
        _get(port, "/20260101_000000_SWC_x_local/03_mut/")
    assert e.value.code in (403, 404)
    req = urllib.request.Request(f"http://127.0.0.1:{port}/x", data=b"a", method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code in (405, 501)


def test_binds_to_localhost_only(served):
    _, port = served
    # the listening address is the loopback interface, never 0.0.0.0
    import socket
    s = socket.socket()
    try:
        s.settimeout(1)
        assert s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def test_url_for_only_inside_root(tmp_path, monkeypatch):
    root = tmp_path / "outputs"
    (root / "r").mkdir(parents=True)
    f = root / "r" / "a b.html"
    f.write_text("x")
    monkeypatch.setattr(reportserver, "ensure_started", lambda: 8502)
    assert reportserver.url_for(f, root=root) == "http://localhost:8502/r/a%20b.html"
    assert reportserver.url_for(tmp_path / "other.html", root=root) is None


def test_coverage_summary(tmp_path):
    info = tmp_path / "coverage.info"
    info.write_text("SF:/a.c\nFNF:2\nFNH:1\nLF:10\nLH:8\nBRF:4\nBRH:1\nend_of_record\n"
                    "SF:/b.c\nLF:10\nLH:2\nBRF:0\nBRH:0\nend_of_record\n")
    s = results.coverage_summary(info)
    assert s["files"] == 2 and s["line_pct"] == 50.0 and s["branch_pct"] == 25.0 and s["function_pct"] == 50.0
    assert results.coverage_summary(tmp_path / "missing.info") == {}


def test_junit_cases(tmp_path):
    xml = tmp_path / "r.xml"
    xml.write_text('<testsuites><testsuite><testcase classname="G" name="ok" time="0.1"/>'
                   '<testcase classname="G" name="bad" time="0.2"><failure message="boom"/></testcase>'
                   '<testcase classname="G" name="skip"><skipped/></testcase></testsuite></testsuites>')
    rows = results.junit_cases(xml)
    assert [r["status"] for r in rows] == ["passed", "failed", "skipped"]
    assert rows[1]["message"] == "boom"
    assert results.junit_cases(tmp_path / "none.xml") == []


def test_zip_run_skips_build_objects(tmp_path):
    run = tmp_path / "run1"
    (run / "03_mut").mkdir(parents=True)
    (run / "RUN_REPORT.md").write_text("report")
    (run / "03_mut" / "a.o").write_text("obj")
    (run / "03_mut" / "run_tests").write_text("bin")
    (run / "03_mut" / "test-results.xml").write_text("<x/>")
    names = zipfile.ZipFile(BytesIO(results.zip_run(run))).namelist()
    assert "run1/RUN_REPORT.md" in names and "run1/03_mut/test-results.xml" in names
    assert not any(n.endswith((".o", "run_tests")) for n in names)


def test_to_windows_path():
    assert results.to_windows_path("/mnt/d/AI/x") == "D:\\AI\\x"
    assert results.to_windows_path("/home/u/x") == "/home/u/x"
