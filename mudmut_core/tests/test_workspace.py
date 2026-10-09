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
