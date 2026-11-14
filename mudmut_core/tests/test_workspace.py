from mudmut_core.workspace import Run


def test_run_create_and_persist(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path)
    assert run.folder.is_dir()
    assert run.path("state.json").is_file()
    assert "SWC_Test" in run.folder.name

    run.save_text("mud_spec.md", "# spec")
    run.save_json("trace.json", {"a": 1})
    assert run.read_text("mud_spec.md") == "# spec"
    assert run.read_json("trace.json") == {"a": 1}


def test_run_load_roundtrip(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path)
    run.save_state(foo="bar")
    loaded = Run.load(run.folder)
    assert loaded.swc == "SWC_Test"
    assert loaded.state.get("foo") == "bar"


def test_list_runs(tmp_path):
    r1 = Run.create("SWC_A", root=tmp_path)
    r2 = Run.create("SWC_B", root=tmp_path)
    names = {r.folder.name for r in Run.list_runs(root=tmp_path)}
    assert r1.folder.name in names
    assert r2.folder.name in names


def test_damaged_state_json_does_not_break_the_run_list(tmp_path):
    good = Run.create("SWC_Good", root=tmp_path)
    bad = Run.create("SWC_Bad", root=tmp_path)
    bad.path("state.json").write_text('{"swc": "SWC_Bad", "pres', encoding="utf-8")   # killed mid-write

    runs = {r.folder.name: r for r in Run.list_runs(root=tmp_path)}

    assert good.folder.name in runs and runs[good.folder.name].damaged == ""
    assert runs[bad.folder.name].damaged          # listed, and marked
    assert runs[bad.folder.name].swc == bad.folder.name


def test_damaged_json_files_read_as_default(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path)
    run.path("run.json").write_text("{not json", encoding="utf-8")
    (run.dir("mut") / "results.json").write_text("", encoding="utf-8")
    assert run.read_json("run.json") is None
    assert run.read_json("run.json", {}) == {}
    assert run.read_json_in("mut", "results.json", {"x": 1}) == {"x": 1}


def test_save_json_leaves_no_temp_file(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path)
    run.save_json("run.json", {"a": 1})
    assert run.read_json("run.json") == {"a": 1}
    assert not list(run.folder.glob("*.tmp"))


def test_run_status_running_done_and_interrupted(tmp_path):
    run = Run.create("SWC_Test", root=tmp_path)
    assert run.status == ""                       # older runs: unknown
    run.mark_running()
    assert Run.load(run.folder).status == "running"   # this process is alive
    run.mark_finished("done")
    assert Run.load(run.folder).status == "done"

    run.save_state(status="running", pid=2 ** 22 + 12345)   # a process that does not exist
    assert Run.load(run.folder).status == "interrupted"
