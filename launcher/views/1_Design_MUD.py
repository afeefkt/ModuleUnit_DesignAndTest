"""Design (MUD): import → plan → spec → review → activity → C skeleton."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import aio, compilable, design, workspace  # noqa: E402


SAMPLE = _REPO_ROOT / "inputs" / "requirements" / "samples" / "bms_requirements.csv"


def _expected(stage: str) -> float:
    """Expected seconds for a stage (measured average, else the default share) — drives the % bar."""
    from mudmut_core import progress as progress_mod
    return progress_mod.expected_seconds(quick=False).get(stage, 120.0)


def _render_mermaid(mmd: str, height: int = 500):
    c.render_mermaid(mmd, height=height)


st.title("Requirements & design")

# ── 1. import ─────────────────────────────────────────────────────────────────
st.header("① Requirements")
use_sample = st.checkbox("Use sample (BMS)", value=True)
uploaded = st.file_uploader(
    "…or upload requirements (.csv / .xlsx / .reqif / .txt / .md) — DOORS, Polarion, Jira, Excel exports",
    type=["csv", "txt", "md", "xlsx", "reqif", "reqifz"],
)


def _header_row(file) -> list[str]:
    """Column headers of an uploaded CSV/XLSX (empty list for other formats)."""
    import csv
    import io
    name = file.name.lower()
    try:
        if name.endswith(".csv"):
            from mudtool.importers.base import read_text_file
            tmp = _REPO_ROOT / "workspace" / "uploads" / ("_hdr_" + file.name)
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(file.getvalue())
            text, _ = read_text_file(tmp)
            tmp.unlink(missing_ok=True)
            first = text.splitlines()[0] if text else ""
            delim = max(",;	|", key=first.count)
            return [h.strip() for h in next(csv.reader(io.StringIO(first), delimiter=delim), []) if h.strip()]
        if name.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file.getvalue()), read_only=True, data_only=True)
            row = next(wb.active.iter_rows(min_row=1, max_row=1, values_only=True), ())
            wb.close()
            return [str(v).strip() for v in row if v]
    except Exception:  # noqa: BLE001 - preview only; the importer reports real errors
        pass
    return []


mapping: dict[str, str] = {}
if uploaded is not None and not use_sample:
    headers = _header_row(uploaded)
    if headers:
        with st.expander("Column mapping (optional — leave on auto unless the import misses columns)"):
            st.caption(f"Detected columns: {', '.join(headers)}")
            for field, label in (("req_id", "ID"), ("title", "Title"), ("description", "Description (text)")):
                choice = st.selectbox(label, ["(auto)"] + headers, key=f"map_{field}")
                if choice != "(auto)":
                    mapping[field] = choice

if st.button("Import requirements", type="primary"):
    if use_sample:
        path = SAMPLE
    elif uploaded is not None:
        path = _REPO_ROOT / "workspace" / "uploads" / uploaded.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(uploaded.getvalue())
    else:
        st.error("Upload a file or use the sample.")
        st.stop()
    result = design.import_requirements(path, column_mapping=mapping or None)
    if not result.requirement_set.requirements:
        st.error(f"Import failed: {result.errors}")
        st.stop()
    st.session_state["imported"] = result.requirement_set
    st.success(f"Imported {result.requirement_set.count} requirement(s)"
               + (f" ({result.rows_skipped} row(s) skipped)" if result.rows_skipped else ""))
    if result.warnings or result.errors:
        with st.expander(f"Import notes ({len(result.warnings) + len(result.errors)})"):
            for msg in result.errors:
                st.error(msg)
            for msg in result.warnings[:50]:
                st.caption(msg)

reqs = st.session_state.get("imported")
if reqs is not None:
    text = design.requirements_text(reqs)
    st.dataframe(design.requirements_to_dicts(reqs), height=200)

    # ── 2. plan ───────────────────────────────────────────────────────────────
    st.header("② Plan modules")
    if st.button("Plan SWC modules"):
        with st.status("Planning modules…", expanded=True) as status:
            plan = c.run_with_progress("Planning modules", lambda report: aio.run_sync(design.plan_modules(text)), _expected("plan"))
            st.session_state["plan"] = plan
            status.update(label="Done", state="complete")
    plan = st.session_state.get("plan")
    if plan is not None:
        names = [m.swc_name for m in plan.modules]
        choice = st.selectbox("Select SWC", names)
        module = next(m for m in plan.modules if m.swc_name == choice)
        st.caption(plan.architecture_summary)

        # ── 3. spec ───────────────────────────────────────────────────────────
        st.header("③ MUD spec")
        mode = "single_pass" if st.checkbox("Quick (single-pass)", value=True) else "two_stage"
        if st.button("Generate MUD spec"):
            with st.status("Generating spec…", expanded=True) as status:
                spec_md = c.run_with_progress("Generating the MUD spec", lambda report: aio.run_sync(design.generate_mud_spec(module, text, mode=mode)), _expected("spec"))
                st.session_state["spec_md"] = spec_md
                st.session_state["module"] = module
                status.update(label="Spec generated", state="complete")
        spec_md = st.session_state.get("spec_md")
        if spec_md:
            st.text_area("MUD spec", spec_md, height=300)

            # ── 4. review ─────────────────────────────────────────────────────
            st.header("④ Review")
            c1, c2 = st.columns(2)
            if c1.button("Review"):
                with st.status("Reviewing…", expanded=True) as status:
                    review = c.run_with_progress("Reviewing the spec", lambda report: aio.run_sync(design.review_spec(module, text, spec_md)), _expected("review"))
                    st.session_state["review"] = review
                    status.update(label="Reviewed", state="complete")
            if c2.button("Approve & continue") and st.session_state.get("review"):
                st.session_state["approved"] = True
            review = st.session_state.get("review")
            if review is not None:
                st.metric("Coverage", f"{review.coverage_pct}%")
                st.metric("Issues", f"{review.error_count} errors / {review.warning_count} warnings")
                if st.button("Improve (regenerate)"):
                    with st.status("Improving…", expanded=True) as status:
                        spec_md, review = c.run_with_progress("Improving the spec", lambda report: aio.run_sync(design.review_and_improve(module, text, spec_md, max_rounds=1)), _expected("review"))
                        st.session_state["spec_md"] = spec_md
                        st.session_state["review"] = review
                        status.update(label="Improved", state="complete")
                        st.rerun()

            # ── 5. activity ───────────────────────────────────────────────────
            st.header("⑤ Activity flow")
            if st.button("Generate flow chart"):
                with st.status("Generating activity…", expanded=True) as status:
                    activity = c.run_with_progress("Generating the activity flow", lambda report: aio.run_sync(design.generate_activity(reqs, spec_md, module.swc_name)), _expected("activity"))
                    st.session_state["activity"] = activity
                    status.update(label="Activity generated", state="complete")
            activity = st.session_state.get("activity")
            if activity is not None:
                exported = design.export(activity)
                c_map = exported["c"]
                mmd_map = exported["mermaid"]
                flow = next(iter(mmd_map.values()), "")
                st.subheader("Flow chart")
                _render_mermaid(flow, height=650)
                with st.expander("Mermaid source"):
                    st.code(flow, language="mermaid")

                # ── 6. C skeleton + compilability ─────────────────────────────
                st.header("⑥ C skeleton")
                code = "\n\n".join(c_map.values())
                if st.button("Make compilable"):
                    run = workspace.Run.create(module.swc_name)
                    project_dir = run.dir("code")
                    rep = compilable.make_compilable(code, module.swc_name, project_dir)
                    run.save_in("mud", "mud_spec.md", spec_md)
                    run.save_in("code", f"{module.swc_name}.c", rep.c_code)
                    run.save_in("mud", "flow.mmd", flow)
                    run.save_json_in("code", "compilability.json", {
                        "total": rep.total_statements, "kept": rep.kept_statements,
                        "stubbed": rep.stubbed_statements, "compile_ok": rep.compile_ok,
                    })
                    st.session_state["current_run_folder"] = str(run.folder)
                    st.session_state["compilability"] = rep
                rep = st.session_state.get("compilability")
                if rep is not None:
                    st.success(rep.summary())
                    st.code(rep.c_code, language="c")
                    if st.button("Send to MUT →"):
                        st.switch_page("views/2_Unit_Tests_MUT.py")
