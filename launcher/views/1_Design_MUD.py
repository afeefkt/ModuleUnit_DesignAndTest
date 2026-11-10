"""Design (MUD): import → plan → spec → review → activity → C skeleton, step by step.

Every model step runs in the background (live bar + Cancel, the page stays usable) and is saved into
one run folder per component — the same files, ``run.json`` and ``RUN_REPORT.md`` a Full chain run
writes — so the run can be continued on the Unit tests page and reviewed in Runs & reports.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import aio, chain, compilable, design, design_run, spec_check  # noqa: E402
from mudmut_core import progress as progress_mod  # noqa: E402
from mudmut_core.workspace import Run  # noqa: E402

SAMPLE = _REPO_ROOT / "inputs" / "requirements" / "samples" / "bms_requirements.csv"
UPLOADS = _REPO_ROOT / "workspace" / "uploads"
SRC_SAMPLE, SRC_FILE, SRC_UPLOAD = "Sample (BMS)", "File from inputs/", "Upload a file"
ss = st.session_state

# Design state, in pipeline order (all "design_" keys are cleared by Reset view). Redoing a step
# clears everything after it, so nothing on screen is built from an older result.
_DOWNSTREAM = ["design_plan", "design_spec_md", "design_spec_swc", "design_run", "design_spec_check",
               "design_review", "design_activity", "design_flow", "design_c_code", "design_comp"]


def _clear_from(key: str) -> None:
    for k in _DOWNSTREAM[_DOWNSTREAM.index(key):]:
        ss.pop(k, None)


def _expected(stage: str) -> float:
    """Expected seconds for a stage (measured average, else the default share) — drives the % bar."""
    return progress_mod.expected_seconds(quick=False).get(stage, 120.0)


def _done(step: str, message: str) -> None:
    """Remember a success message for ``step`` and redraw (the run bar shows the new verdicts)."""
    ss["design_flash"] = (step, message)
    st.rerun()


def _flash(step: str) -> None:
    flash = ss.get("design_flash")
    if flash and flash[0] == step:
        ss.pop("design_flash", None)
        st.success(flash[1])


def _run() -> Run | None:
    folder = ss.get("design_run")
    if folder and Path(folder).is_dir():
        return Run.load(folder)
    return None


def _header_row(name: str, data: bytes) -> list[str]:
    """Column headers of a CSV/XLSX file (empty list for other formats or on any read problem)."""
    import csv
    import io
    lower = name.lower()
    try:
        if lower.endswith(".csv"):
            from mudtool.importers.base import read_text_file
            tmp = UPLOADS / ("_hdr_" + Path(name).name)
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            text, _ = read_text_file(tmp)
            tmp.unlink(missing_ok=True)
            first = text.splitlines()[0] if text else ""
            delim = max(",;	|", key=first.count)
            return [h.strip() for h in next(csv.reader(io.StringIO(first), delimiter=delim), []) if h.strip()]
        if lower.endswith(".xlsx"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            row = next(wb.active.iter_rows(min_row=1, max_row=1, values_only=True), ())
            wb.close()
            return [str(v).strip() for v in row if v]
    except Exception:  # noqa: BLE001 - preview only; the importer reports real errors
        pass
    return []


st.title("Requirements & design")
st.caption("Step by step from requirements to a compilable C skeleton. Each model step runs in the background "
           "with a **Cancel** button, and every result is saved in one run folder per component (the same files "
           "and report as **Full chain**). Continue with **Unit tests**.")
busy = c.any_step_running()
if busy:
    st.caption("A job is running — the step buttons are available again when it finishes.")

# ── 1. import ─────────────────────────────────────────────────────────────────
st.header("① Requirements")
source = st.radio("Requirements from", [SRC_SAMPLE, SRC_FILE, SRC_UPLOAD], horizontal=True, key="dsg_source")
path: Path | None = None
uploaded = None
if source == SRC_SAMPLE:
    path = SAMPLE
    st.caption(f"`{c.file_label(SAMPLE)}`")
elif source == SRC_FILE:
    files = c.requirement_files()
    extra = ss.get("dsg_extra_file")   # a hardened baseline handed over from Harden requirements
    if extra and Path(extra).is_file() and Path(extra) not in files:
        files.append(Path(extra))
    if ss.get("dsg_file") not in [c.file_label(p) for p in files]:
        ss.pop("dsg_file", None)       # the remembered file is gone: fall back to the first one
    if files:
        labels = [c.file_label(p) for p in files]
        pick = st.selectbox("Requirements file", labels, key="dsg_file",
                            help="Files under inputs/requirements*/ — hardened baselines are marked.")
        path = files[labels.index(pick)]
    else:
        st.info("No requirement files under `inputs/requirements*/`. Upload one instead.")
else:
    uploaded = st.file_uploader(
        "Upload requirements (.csv / .xlsx / .reqif / .txt / .md) — DOORS, Polarion, Jira, Excel exports",
        type=["csv", "txt", "md", "xlsx", "reqif", "reqifz"], key="dsg_upload",
    )

mapping: dict[str, str] = {}
if source != SRC_SAMPLE and (uploaded is not None or path is not None):
    try:
        headers = _header_row(uploaded.name, uploaded.getvalue()) if uploaded is not None else \
            _header_row(path.name, path.read_bytes())
    except OSError:
        headers = []
    if headers:
        with st.expander("Column mapping (optional — leave on auto unless the import misses columns)"):
            st.caption(f"Detected columns: {', '.join(headers)}")
            for field, label in (("req_id", "ID"), ("title", "Title"), ("description", "Description (text)")):
                choice = st.selectbox(label, ["(auto)"] + headers, key=f"map_{field}")
                if choice != "(auto)":
                    mapping[field] = choice

can_import = not busy and (uploaded is not None if source == SRC_UPLOAD else path is not None)
if st.button("Import requirements", type="primary", disabled=not can_import):
    from mudmut_core import settings as _settings
    if _settings.auto_reset_enabled():
        c.reset_view()   # a new import starts a new design: drop the previous run's screen state
    if uploaded is not None:
        path = UPLOADS / Path(uploaded.name).name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(uploaded.getvalue())
    try:
        result = design.import_requirements(path, column_mapping=mapping or None)
    except Exception as exc:  # noqa: BLE001 - a broken or unsupported file
        result = None
        st.error(f"Could not read `{path.name}`: {exc}")
    if result is not None and not result.requirement_set.requirements:
        st.error(f"No requirements recognised in `{path.name}`: {result.errors or 'check the column mapping'}")
    elif result is not None:
        _clear_from("design_plan")
        ss["design_reqs"] = result.requirement_set
        ss["design_source_path"] = str(path)
        st.success(f"Imported {result.requirement_set.count} requirement(s) from `{path.name}`"
                   + (f" ({result.rows_skipped} row(s) skipped)" if result.rows_skipped else ""))
        if result.warnings or result.errors:
            with st.expander(f"Import notes ({len(result.warnings) + len(result.errors)})"):
                for msg in result.errors:
                    st.error(msg)
                for msg in result.warnings[:50]:
                    st.caption(msg)

reqs = ss.get("design_reqs")
if reqs is None:
    st.stop()
st.caption(f"Imported from `{Path(ss.get('design_source_path', '')).name}`")
st.dataframe(design.requirements_to_dicts(reqs), height=200)
text_all = design.requirements_text(reqs)

# ── 2. plan ───────────────────────────────────────────────────────────────────
st.header("② Plan modules")
out = c.step_outcome("design_plan")
if out and out.ok:
    _clear_from("design_plan")
    ss["design_plan"] = out.result
    _done("plan", f"Planned {len(out.result.modules)} software component(s).")
elif out and not out.running:
    c.show_step_failure(out, "Planning")
_flash("plan")
if st.button("Plan SWC modules", disabled=busy):
    c.start_step("design_plan", "Planning modules",
                 lambda report, t=text_all: aio.run_sync(design.plan_modules(t)), expected_seconds=_expected("plan"))
    st.rerun()

plan = ss.get("design_plan")
if plan is None:
    st.stop()
if not plan.modules:
    st.error("The planner returned no software components. Plan again, or pick another model on **Models**.")
    st.stop()
names = [m.swc_name for m in plan.modules]
choice = st.selectbox("Software component", names, key="dsg_swc")
module = next(m for m in plan.modules if m.swc_name == choice)
st.caption(plan.architecture_summary)
module_reqs = chain.requirements_for_module(reqs, module)
if module_reqs is not reqs:
    st.caption(f"{module_reqs.count} of {reqs.count} requirements were planned for {choice}; only those go to the model.")

# ── 3. spec ───────────────────────────────────────────────────────────────────
st.header("③ MUD spec")
out = c.step_outcome("design_spec")
if out and out.ok:
    swc, quick_used = out.context["swc"], out.context["quick"]
    spec_md = out.result or ""
    if len(spec_md.strip()) < 200:
        st.error(f"The model returned only {len(spec_md.strip())} characters for the spec of {swc}. "
                 "Generate again, or pick a stronger model on **Models**.")
    else:
        smod = next((m for m in plan.modules if m.swc_name == swc), module)
        try:
            run = design_run.start(swc, chain.requirements_for_module(reqs, smod),
                                   source=Path(ss.get("design_source_path", "")), quick=quick_used)
            run.save_in("mud", "mud_spec.md", spec_md)
            sc = spec_check.check_spec(spec_md, swc)
            run.save_json_in("mud", "spec_check.json", sc)
            design_run.record_step(run, "spec", note=f"{len(spec_md)} chars, mode={'single_pass' if quick_used else 'two_stage'}")
        except OSError as exc:
            st.error(f"Could not write the run folder: {exc}")
        else:
            _clear_from("design_spec_md")
            ss.update(design_spec_md=spec_md, design_spec_swc=swc, design_run=str(run.folder),
                      design_spec_check=sc, design_quick_used=quick_used, design_spec_reload=True)
            c.select_run(run.folder)
            _done("spec", f"Spec generated for {swc} and saved in `{run.folder.name}`.")
elif out and not out.running:
    c.show_step_failure(out, "Spec generation")
_flash("spec")
quick = st.checkbox("Quick (single-pass)", value=True, key="dsg_quick",
                    help="One model call for the spec. Off: skeleton + generator (two stages), slower.")
if st.button("Generate MUD spec", disabled=busy,
             help="Each new spec starts a new run folder for this component."):
    mode = "single_pass" if quick else "two_stage"
    c.start_step("design_spec", f"Generating the MUD spec for {module.swc_name}",
                 lambda report, m=module, t=design.requirements_text(module_reqs), md=mode:
                 aio.run_sync(design.generate_mud_spec(m, t, mode=md)),
                 expected_seconds=_expected("spec"), context={"swc": module.swc_name, "quick": quick})
    st.rerun()

spec_md = ss.get("design_spec_md")
if not spec_md:
    st.stop()
run = _run()
if run is None:
    st.warning("The run folder of this design is gone (archived or deleted). Generate the spec again.")
    st.stop()
spec_swc = ss["design_spec_swc"]
if spec_swc != module.swc_name:
    st.warning(f"This spec was made for **{spec_swc}**, so the steps below still design {spec_swc}. "
               f"Press **Generate MUD spec** to design {module.swc_name}.")
smod = next((m for m in plan.modules if m.swc_name == spec_swc), module)
sreqs = chain.requirements_for_module(reqs, smod)
stext = design.requirements_text(sreqs)

sc = ss.get("design_spec_check")
if not sc:
    sc = ss["design_spec_check"] = spec_check.check_spec(spec_md, spec_swc)
if not sc.get("ok"):
    st.error("Spec check (no AI): " + " ".join(sc.get("problems") or []) +
             " Full chain would stop here — regenerate the spec, edit it, or use a stronger model.")
for w in spec_check.warnings_for(sc, spec_swc):
    st.warning(w)
# The editor shows the saved spec; it is refilled (before the widget is drawn) whenever a step
# replaces the spec, so an older text never stays in the box.
if ss.pop("design_spec_reload", False) or "design_spec_edit" not in ss:
    ss["design_spec_edit"] = spec_md
edited = st.text_area("MUD spec (you can edit it)", key="design_spec_edit", height=300)
if edited != spec_md:
    st.caption("Unsaved edits — the steps below use the saved spec until you press **Save my edits**. "
               "Saving clears the review, flow chart and C code made from the old text.")
    if st.button("Save my edits", disabled=busy):
        run.save_in("mud", "mud_spec.md", edited)
        sc = spec_check.check_spec(edited, spec_swc)
        run.save_json_in("mud", "spec_check.json", sc)
        design_run.record_step(run, "spec", note=f"{len(edited)} chars, edited by hand")
        _clear_from("design_review")
        ss.update(design_spec_md=edited, design_spec_check=sc)
        _done("spec", "Your edits are saved in the run folder.")

# ── 4. review ─────────────────────────────────────────────────────────────────
st.header("④ Review")
out = c.step_outcome("design_review")
if out and out.ok:
    review = out.result
    note = ""
    if out.context.get("kind") == "improve":
        improved, review = out.result
        if improved and improved != spec_md:
            sc_new = spec_check.check_spec(improved, spec_swc)
            worse = (not sc_new["ok"]) or len(sc_new["usable"]) < len(sc.get("usable") or []) \
                or spec_check.gap_count(sc_new) > spec_check.gap_count(sc)
            if worse:
                run.save_in("mud", "mud_spec_review_rejected.md", improved)
                note = "; rewrite discarded (failed the spec check)"
                st.warning("The improved spec was worse in the spec check, so the saved spec was kept "
                           "(the rewrite is in `01_mud/mud_spec_review_rejected.md`).")
            else:
                run.save_in("mud", "mud_spec.md", improved)
                run.save_json_in("mud", "spec_check.json", sc_new)
                design_run.record_step(run, "spec", note=f"{len(improved)} chars, improved by the review")
                ss.update(design_spec_md=improved, design_spec_check=sc_new, design_spec_reload=True)
                note = "; rewrite kept"
    run.save_json_in("mud", "review.json", review.to_dict())
    design_run.record_step(
        run, "review", note=f"approved={review.approved} coverage={review.coverage_pct}%{note}",
        review_approved=bool(review.approved), review_ai_empty=bool(getattr(review, "ai_review_empty", False)))
    _clear_from("design_review")
    ss["design_review"] = review
    _done("review", f"Review finished: coverage {review.coverage_pct} %, "
                    f"{review.error_count} error(s), {review.warning_count} warning(s).")
elif out and not out.running:
    c.show_step_failure(out, "The review")
_flash("review")
r1, r2 = st.columns(2)
if r1.button("Review", disabled=busy):
    c.start_step("design_review", "Reviewing the spec",
                 lambda report, m=smod, t=stext, s=spec_md: aio.run_sync(design.review_spec(m, t, s)),
                 expected_seconds=_expected("review"), context={"kind": "review"})
    st.rerun()
if r2.button("Review and improve (one round)", disabled=busy,
             help="The model reviews the spec and rewrites it once; the rewrite is kept only if the spec check "
                  "does not get worse."):
    c.start_step("design_review", "Improving the spec",
                 lambda report, m=smod, t=stext, s=spec_md: aio.run_sync(design.review_and_improve(m, t, s, max_rounds=1)),
                 expected_seconds=2 * _expected("review"), context={"kind": "improve"})
    st.rerun()
review = ss.get("design_review")
if review is not None:
    m1, m2, m3 = st.columns(3)
    m1.metric("Approved", "yes" if review.approved else "no")
    m2.metric("Coverage", f"{review.coverage_pct}%")
    m3.metric("Issues", f"{review.error_count} errors / {review.warning_count} warnings")
else:
    st.caption("Optional — Full chain skips it in quick mode. Without a review the run report shows it as not run.")

# ── 5. activity ───────────────────────────────────────────────────────────────
st.header("⑤ Activity flow")
out = c.step_outcome("design_activity")
if out and out.ok:
    activity = out.result
    if not getattr(activity, "diagrams", None):
        reason = "; ".join(getattr(activity, "errors", None) or []) or "no diagrams produced"
        st.error(f"The activity step produced no flow chart: {reason}")
    else:
        try:
            exported = design.export(activity)
        except Exception as exc:  # noqa: BLE001 - exporter problem on this activity
            st.error(f"Could not export the flow chart to C and Mermaid: {exc}")
        else:
            flow = next(iter(exported["mermaid"].values()), "")
            code = "\n\n".join(exported["c"].values())
            if not code:
                st.error("The flow chart has no top-level activity, so no C skeleton could be made.")
            else:
                run.save_json_in("mud", "activity.json",
                                 activity.model_dump() if hasattr(activity, "model_dump") else activity.dict())
                run.save_in("mud", "flow.mmd", flow)
                run.save_in("code", f"{spec_swc}.c", code)
                design_run.record_step(run, "activity", note=f"{len(activity.diagrams)} diagram(s)"
                                       + ("" if out.context.get("ai") else ", built from Section 7 (no AI)"))
                _clear_from("design_activity")
                ss.update(design_activity=activity, design_flow=flow, design_c_code=code)
                _done("activity", f"Flow chart generated ({len(activity.diagrams)} diagram(s)).")
elif out and not out.running:
    c.show_step_failure(out, "The activity flow")
_flash("activity")
use_ai = st.checkbox("Build the flow with AI (slower)", value=not ss.get("design_quick_used", True),
                     key="dsg_activity_ai",
                     help="Off: the flow is built directly from Section 7 of the spec, as Full chain does in quick mode.")
if st.button("Generate flow chart", disabled=busy):
    c.start_step("design_activity", "Generating the activity flow",
                 lambda report, r=sreqs, s=spec_md, w=spec_swc, ai=use_ai:
                 aio.run_sync(design.generate_activity(r, s, w, use_ai=ai)),
                 expected_seconds=_expected("activity"), context={"ai": use_ai})
    st.rerun()

flow = ss.get("design_flow")
code = ss.get("design_c_code")
if ss.get("design_activity") is None or not code:
    st.stop()
st.subheader("Flow chart")
c.render_mermaid(flow, height=650, alt=f"Activity flow of {spec_swc}")
with st.expander("Mermaid source"):
    st.code(flow, language="mermaid")

# ── 6. C skeleton + compilability ─────────────────────────────────────────────
st.header("⑥ C skeleton")
out = c.step_outcome("design_compilable")
if out and out.ok:
    rep = out.result
    run.save_in("code", f"{spec_swc}.c", rep.c_code)
    run.save_json_in("code", "compilability.json", design_run.compilability_json(rep, spec_swc))
    design_run.record_step(run, "compilable", note=rep.summary())
    ss["design_comp"] = rep
    _done("compilable", f"Compile check finished: {rep.summary()}")
elif out and not out.running:
    c.show_step_failure(out, "The compile check")
_flash("compilable")
with st.expander("C skeleton from the flow chart (before the compile check)"):
    st.code(code, language="c")
if st.button("Make compilable", type="primary", disabled=busy,
             help="Compiles with gcc in WSL, declares missing symbols and comments out only what still fails."):
    c.start_step("design_compilable", "Making the C skeleton compilable",
                 lambda report, src=code, w=spec_swc, d=run.dir("code"), s=spec_md:
                 compilable.make_compilable(src, w, d, spec_md=s),
                 expected_seconds=_expected("compilable") or 60.0, cancellable=False)
    st.rerun()
rep = ss.get("design_comp")
if rep is not None:
    clean = rep.compile_ok and not (rep.logic_stubbed or rep.never_assigned or rep.dropped_arguments)
    (st.success if clean else st.warning)(rep.summary())
    for note in (run.read_json("run.json") or {}).get("quality_notes") or []:
        st.markdown(note)
    with st.expander("Compilable C", expanded=False):
        st.code(rep.c_code, language="c")
    st.page_link("views/2_Unit_Tests_MUT.py", label=f"Continue with Unit tests for {spec_swc}", icon="🧪")
