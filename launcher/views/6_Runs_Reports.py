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
    comp = data.get("compilability") or {}
    tests = data.get("tests") or {}
    junit = tests.get("junit") or {}
    cov = results.coverage_summary(r.dir("mut") / "coverage.info")
    verdicts = effective_verdicts(data)
    timings = data.get("timings") or {}
    stamp = r.created_key
    when = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]}" if len(stamp) >= 13 else stamp
    return {
        "run": r.folder.name,
        "created": when,
        "SWC": r.swc,
        "preset": r.preset,
        "data": ", ".join(data.get("cloud_providers") or []) or "local",
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
event = st.dataframe(
    shown, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="runs_table",
    column_config={
        "run": st.column_config.TextColumn("Run folder", width="medium"),
        "verdicts": st.column_config.TextColumn("Stages", help="Import · Plan · Spec · Review · Activity · "
                                                "Compilable · Tests · Build & run · Trace"),
        "line cov %": st.column_config.NumberColumn("Line coverage %", format="%.1f"),
        "smoke only": st.column_config.CheckboxColumn("Smoke test only",
                                                      help="No AI-written test compiled — results prove nothing"),
    },
)
picked_rows = (event.selection.rows if event and getattr(event, "selection", None) else [])
if picked_rows:
    picked = shown[picked_rows[0]]["run"]
    if picked != Path(st.session_state.get("current_run_folder", "")).name:
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
        report = run.read_text("RUN_REPORT.md", "")
        st.subheader("Test results and coverage")
        c.results_panel(run, key="runs")
        st.subheader("Run report")
        st.markdown(report or "_No report_")
        with st.expander("MUD spec"):
            st.markdown(run.read_in("mud", "mud_spec.md", "(none)"))
        with st.expander("Flow chart"):
            c.render_mermaid(run.read_in("mud", "flow.mmd", ""), height=520)
        with st.expander("C skeleton"):
            st.code(run.read_in("code", f"{run.swc}.c", "(none)"), language="c")
        with st.expander("Trace"):
            st.json(run.read_json_in("trace", "trace.json", {}))

elif mode == "Compare two runs":
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Run A**")
        a = c.run_picker("compare_a")
    with col_b:
        st.markdown("**Run B**")
        b = c.run_picker("compare_b")
    if a and b:
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
    names = [r.folder.name for r in runs]
    to_archive = st.multiselect("Runs to archive", names)
    if st.button("Archive selected runs", disabled=not to_archive):
        from mudmut_core import jobs
        if jobs.any_running():
            st.warning("A run is in progress — archive after it finishes.")
        else:
            for name in to_archive:
                next(r for r in runs if r.folder.name == name).archive()
            st.session_state.pop("current_run_folder", None)
            c._bump_bar()
            st.success(f"Archived {len(to_archive)} run(s).")
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
                st.rerun()
            except (FileExistsError, FileNotFoundError) as exc:
                st.error(str(exc))
