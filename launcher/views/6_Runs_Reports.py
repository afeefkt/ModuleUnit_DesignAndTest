"""Runs & Reports — a table of all runs, one run's evidence, and a side-by-side compare."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import results  # noqa: E402
from mudmut_core.report import effective_verdicts  # noqa: E402
from mudmut_core.workspace import Run  # noqa: E402

st.title("Runs & reports")

runs = c.list_runs()
if not runs:
    st.info("No runs yet — run the Design, Full chain, or OpenCode agent page first.")
    st.stop()

_STAGES = [("import", "Import"), ("plan", "Plan"), ("spec", "Spec"), ("review", "Review"), ("activity", "Activity"),
           ("compilable", "Compilable"), ("generate_tests", "Tests"), ("build_run", "Build & run"), ("trace", "Trace")]


def _row(r: Run) -> dict:
    data = r.read_json("run.json") or {}
    if not isinstance(data, dict):
        data = {}
    comp = data.get("compilability") or {}
    tests = data.get("tests") or {}
    junit = tests.get("junit") or {}
    try:
        cov = results.coverage_summary(r.dir("mut") / "coverage.info")
    except Exception:  # noqa: BLE001 - a damaged coverage file must not hide the run
        cov = {}
    verdicts = effective_verdicts(data)
    timings = data.get("timings") or {}
    stamp = r.created_key
    when = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]}" if len(stamp) >= 13 else stamp
    return {
        "run": r.folder.name,
        "created": when,
        "SWC": r.swc,
        "preset": r.preset,
        "state": c.run_status_note(r) or r.status or "",
        "data": ", ".join(str(x) for x in data.get("cloud_providers") or []) or "local",
        "verdicts": " ".join(verdicts.get(k, "·") for k, _ in _STAGES) if verdicts else "no report",
        "C kept / stubbed": f"{comp.get('kept', '')} / {comp.get('stubbed', '')}" if comp else "",
        "tests passed": junit.get("passed"),
        "tests failed": (junit.get("failures") or 0) + (junit.get("errors") or 0) if junit else None,
        "smoke only": bool(tests.get("smoke_fallback")),
        "line cov %": cov.get("line_pct"),
        "minutes": round(sum(v for v in timings.values() if isinstance(v, (int, float))) / 60, 1) if timings else None,
    }


# ── Table of runs ────────────────────────────────────────────────────────────
st.subheader("All runs")
rows = [_row(r) for r in runs]
f1, f2 = st.columns([2, 1])
swcs = sorted({r["SWC"] for r in rows})
pick_swc = f1.multiselect("Show components", swcs, default=[], placeholder="All components")
where = f2.selectbox("Data", ["All runs", "Local only", "Used cloud"])
shown = [r for r in rows if (not pick_swc or r["SWC"] in pick_swc)
         and (where == "All runs" or (where == "Local only") == (r["data"] == "local"))]
# A new table (and so no stale row selection) whenever the filter changes the rows.
table_key = "runs_table_" + str(abs(hash((tuple(pick_swc), where, tuple(r["run"] for r in shown)))))
st.session_state["_runs_table_key"] = table_key
event = st.dataframe(
    shown, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key=table_key,
    column_config={
        "run": st.column_config.TextColumn("Run folder", width="medium"),
        "state": st.column_config.TextColumn("State", help="running · interrupted (the app stopped during the run) "
                                             "· failed · cancelled · damaged files"),
        "verdicts": st.column_config.TextColumn("Stages", help="Import · Plan · Spec · Review · Activity · "
                                                "Compilable · Tests · Build & run · Trace"),
        "line cov %": st.column_config.NumberColumn("Line coverage %", format="%.1f"),
        "smoke only": st.column_config.CheckboxColumn("Smoke test only",
                                                      help="No AI-written test compiled — results prove nothing"),
    },
)
picked_rows = (event.selection.rows if event and getattr(event, "selection", None) else [])
picked = shown[picked_rows[0]]["run"] if picked_rows and picked_rows[0] < len(shown) else None
# Act on a click only (the selection changed). A row that stays selected must not pull the
# current run back when another run is chosen in the top bar.
if picked != st.session_state.get("_runs_table_picked"):
    st.session_state["_runs_table_picked"] = picked
    if picked and picked != Path(st.session_state.get("current_run_folder", "")).name:
        c.select_run(next(r.folder for r in runs if r.folder.name == picked))
        st.rerun()
st.caption("Click a row to make it the current run. ✅ pass · ⚠️ partial · ❌ failed · — not run.")

st.divider()
mode = st.radio("View", ["Single run", "Compare two runs", "Archive"], horizontal=True)

if mode == "Single run":
    run = c.current_run()  # chosen in the run bar at the top of every page
    if run is None:
        st.info("No run selected — click a row in the table above or choose one in the top bar.")
    if run:
        note = c.run_status_note(run)
        if note:
            st.warning(f"`{run.folder.name}`: {note}.")
        st.subheader("Test results and coverage")
        c.results_panel(run, key="runs", show_report=False)
        st.subheader("Run report")
        st.markdown(run.read_text("RUN_REPORT.md", "") or "_No run report — this run did not get far enough to write one._")
        with st.expander("MUD spec"):
            st.markdown(run.read_in("mud", "mud_spec.md", "(none)"))
        with st.expander("Flow chart"):
            c.render_mermaid(run.read_in("mud", "flow.mmd", ""), height=520, alt=f"Activity flow of {run.swc}")
        with st.expander("C skeleton"):
            st.code(run.read_in("code", f"{run.swc}.c", "(none)"), language="c")
        with st.expander("Traceability (requirement → tests)"):
            c.trace_view(run.read_json_in("trace", "trace.json"), key="runs")

elif mode == "Compare two runs":
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Run A**")
        a = c.run_picker("compare_a", index=0)
    with col_b:
        st.markdown("**Run B**")
        b = c.run_picker("compare_b", index=1 if len(runs) > 1 else 0)
    if a and b and a.folder == b.folder:
        st.info("Run A and run B are the same run — pick two different runs.")
    elif a and b:
        ja = a.read_json("run.json") or {}
        jb = b.read_json("run.json") or {}
        ra, rb = _row(a), _row(b)
        st.markdown("**Headline**")
        st.table([{"": k, "A": ra[k], "B": rb[k]} for k in
                  ("SWC", "preset", "data", "C kept / stubbed", "tests passed", "tests failed", "smoke only",
                   "line cov %", "minutes")])
        st.markdown("**Stage verdicts**")
        va, vb = effective_verdicts(ja), effective_verdicts(jb)
        st.table([{"stage": label, "A": va.get(k, "—"), "B": vb.get(k, "—"),
                   "same": "" if va.get(k) == vb.get(k) else "≠"} for k, label in _STAGES])
        st.markdown("**Models per stage**")
        ma, mb = {}, {}
        for side, src in ((ma, ja), (mb, jb)):
            for group in (src.get("models") or {}).values():
                for stage, cfg in (group or {}).items():
                    side[stage] = f"{cfg.get('provider', 'ollama')} / {cfg.get('model', '')}"
        st.table([{"stage": s, "A": ma.get(s, ""), "B": mb.get(s, ""), "same": "" if ma.get(s) == mb.get(s) else "≠"}
                  for s in sorted(set(ma) | set(mb))])
        ta, tb = ja.get("timings") or {}, jb.get("timings") or {}
        keys = [k for k, _ in _STAGES if k in ta or k in tb]
        if keys:
            st.markdown("**Time per stage (seconds)**")
            st.bar_chart({"A": [ta.get(k, 0) for k in keys], "B": [tb.get(k, 0) for k in keys]},
                         x_label="stage", y_label="seconds", stack=False, height=260)
            st.caption("Stages in order: " + ", ".join(keys))

else:
    st.markdown("Archiving moves a run folder to `outputs/_archive/`. Nothing is deleted and you can restore it.")
    from mudmut_core import jobs
    names = [r.folder.name for r in runs]
    to_archive = st.multiselect("Runs to archive", names)
    current_name = Path(st.session_state.get("current_run_folder", "")).name
    sure = False
    if to_archive:
        if current_name in to_archive:
            st.caption(f"`{current_name}` is the current run; the newest remaining run becomes current.")
        sure = st.checkbox(f"Move {len(to_archive)} run(s) to `outputs/_archive/`", key="archive_confirm")
    busy = jobs.any_running()
    if st.button("Archive selected runs", disabled=not (to_archive and sure) or busy,
                 help="A run is in progress — archive after it finishes." if busy else None):
        failed = []
        for name in to_archive:
            try:
                next(r for r in runs if r.folder.name == name).archive()
            except (OSError, StopIteration) as exc:
                failed.append(f"{name}: {exc}")
        if current_name in to_archive:
            st.session_state.pop("current_run_folder", None)
        st.session_state.pop("archive_confirm", None)
        c.bump_bar()
        if failed:
            st.error("Could not archive: " + "; ".join(failed))
        else:
            st.rerun()
    archived = Run.list_archived()
    st.subheader("Archived runs")
    if not archived:
        st.caption("Nothing archived.")
    for r in archived:
        a1, a2 = st.columns([4, 1])
        a1.write(f"`{r.folder.name}` — {r.swc} ({r.preset})")
        if a2.button("Restore", key=f"restore_{r.folder.name}"):
            try:
                Run.restore_archived(r.folder.name)
            except OSError as exc:   # FileExistsError / FileNotFoundError / a locked folder
                st.error(str(exc))
            else:
                c.bump_bar()
                st.rerun()
