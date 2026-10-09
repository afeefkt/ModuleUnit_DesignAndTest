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

st.set_page_config(page_title="Design (MUD)", page_icon="📐", layout="wide")

SAMPLE = _REPO_ROOT / "mud-tool" / "data" / "sample" / "bms_requirements.csv"


def _render_mermaid(mmd: str, height: int = 500):
    st.components.v1.html(
        f"""
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{ startOnLoad: false }});
          mermaid.run({{ querySelector: '.mermaid' }});
        </script>
        <pre class="mermaid" style="font-size:12px">{mmd}</pre>
        """,
        height=height,
    )


st.title("📐 Design (MUD)")

# ── 1. import ─────────────────────────────────────────────────────────────────
st.header("① Requirements")
use_sample = st.checkbox("Use sample (BMS)", value=True)
uploaded = st.file_uploader("…or upload requirements (.csv / .txt / .md / .xlsx)", type=["csv", "txt", "md", "xlsx"])

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
    result = design.import_requirements(path)
    if not result.requirement_set.requirements:
        st.error(f"Import failed: {result.errors}")
        st.stop()
    st.session_state["imported"] = result.requirement_set
    st.success(f"Imported {result.requirement_set.count} requirement(s)")

reqs = st.session_state.get("imported")
if reqs is not None:
    text = design.requirements_text(reqs)
    st.dataframe(design.requirements_to_dicts(reqs), height=200)

    # ── 2. plan ───────────────────────────────────────────────────────────────
    st.header("② Plan modules")
    if st.button("Plan SWC modules"):
        with st.status("Planning modules…", expanded=True) as status:
            plan = aio.run_sync(design.plan_modules(text))
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
                spec_md = aio.run_sync(design.generate_mud_spec(module, text, mode=mode))
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
                    review = aio.run_sync(design.review_spec(module, text, spec_md))
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
                        spec_md, review = aio.run_sync(design.review_and_improve(module, text, spec_md, max_rounds=1))
                        st.session_state["spec_md"] = spec_md
                        st.session_state["review"] = review
                        status.update(label="Improved", state="complete")
                        st.rerun()

            # ── 5. activity ───────────────────────────────────────────────────
            st.header("⑤ Activity flow")
            if st.button("Generate flow chart"):
                with st.status("Generating activity…", expanded=True) as status:
                    activity = aio.run_sync(design.generate_activity(reqs, spec_md, module.swc_name))
                    st.session_state["activity"] = activity
                    status.update(label="Activity generated", state="complete")
            activity = st.session_state.get("activity")
            if activity is not None:
                exported = design.export(activity)
                c_map = exported["c"]
                mmd_map = exported["mermaid"]
                flow = next(iter(mmd_map.values()), "")
                st.subheader("Flow chart")
                _render_mermaid(flow)
                with st.expander("Mermaid source"):
                    st.code(flow, language="mermaid")

                # ── 6. C skeleton + compilability ─────────────────────────────
                st.header("⑥ C skeleton")
                code = "\n\n".join(c_map.values())
                if st.button("Make compilable"):
                    run = workspace.Run.create(module.swc_name)
                    project_dir = run.path("project")
                    project_dir.mkdir(parents=True, exist_ok=True)
                    rep = compilable.make_compilable(code, module.swc_name, project_dir)
                    run.save_text(workspace.MUD_SPEC, spec_md)
                    run.save_text(workspace.SKELETON, rep.c_code)
                    run.save_text(workspace.FLOW, flow)
                    run.save_json(workspace.COMPILABILITY, {
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
                        st.switch_page("pages/2_Unit_Tests_MUT.py")
