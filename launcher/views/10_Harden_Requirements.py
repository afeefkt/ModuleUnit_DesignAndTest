"""Harden requirements — turn a raw export into a reviewable baseline before design.

Runs the deterministic requirements-hardening tool (``requirements_hardening/``): audit → author
(acceptance criteria, verification method, trace, splits of compound requirements) → independent
review → export. The original file is never changed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import hardening  # noqa: E402

st.title("Harden requirements")
st.markdown("Before design, make each requirement atomic and testable: acceptance criteria with boundary values, "
            "a verification method, trace links and a test design. The result is a **draft baseline for human "
            "review** — the original file is not changed.")

if not hardening.available():
    st.error("The hardening tool (`requirements_hardening/`) is not in this checkout.")
    st.stop()

sets = hardening.list_sets()
if not sets:
    st.error("No requirement sets found in `requirements_hardening/data/` (files like `aeb_overrides.json`).")
    st.stop()

# ── Run ──────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([1, 3])
set_name = c1.selectbox("Requirement set", sets, help="Each set has its own curated rules in requirements_hardening/data/.")
files = [p for p in c.requirement_files() if "requirements_hardened" not in p.as_posix()]
labels = [c.file_label(p) for p in files]
default_rel = hardening.default_input(set_name)
default_idx = next((i for i, p in enumerate(files) if default_rel and p.as_posix().endswith(default_rel)), 0)
choice = c2.selectbox("Original requirement file", labels, index=default_idx if files else 0,
                      help="The raw export to harden (CSV). It is copied into the run folder, never modified.")
input_path = files[labels.index(choice)] if files else None
if input_path is not None and default_rel and not input_path.as_posix().endswith(default_rel):
    st.warning(f"The set **{set_name}** has curated rules for `{default_rel}`, but you picked `{c.file_label(input_path)}`. "
               "Its overrides refer to that file's requirement IDs, so the result may be wrong — pick the matching "
               "set or file.")

if st.button("Harden requirements", type="primary", disabled=input_path is None or c.any_step_running()):
    try:
        manifest = c.run_with_progress(
            f"Hardening {set_name}", lambda report: hardening.run(input_path, set_name), expected_seconds=20)
        st.session_state["harden_result"] = manifest.get("run_dir")
        st.success("Hardening finished.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Hardening failed: {exc}")

# ── Results ──────────────────────────────────────────────────────────────────
runs = hardening.list_runs()
if not runs:
    st.info("No hardening run yet. Pick a set and press **Harden requirements**.")
    st.stop()

st.divider()
st.subheader("Hardening runs")
names = [str(r["folder"].name) for r in runs]
wanted = Path(st.session_state.get("harden_result") or "").name
idx = names.index(wanted) if wanted in names else 0
picked = st.selectbox("Run", names, index=idx)
run = runs[names.index(picked)]

before, after = run.get("baseline_metrics") or {}, run.get("hardened_metrics") or {}


def _delta(key: str, digits: int = 0):
    """after − before for a metric, or None when either side is missing or not a number."""
    a, b = after.get(key), before.get(key)
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    d = round(a - b, digits) if digits else a - b
    return d or None


m1, m2, m3, m4 = st.columns(4)
m1.metric("Requirements", after.get("requirements", run.get("hardened_requirements")), delta=_delta("requirements"),
          help="After hardening (compound requirements split into atomic ones, gap requirements added).")
m2.metric("Quality score", after.get("average_score"), delta=_delta("average_score", 1))
m3.metric("Critical findings", after.get("critical"), delta=_delta("critical"), delta_color="inverse")
review = run.get("review") or {}
m4.metric("Blocking reviews", review.get("blocking", 0), help=f"Reviewer: {review.get('reviewer', '')}")
st.caption(f"Status: {run.get('status', '')}")

csv = hardening.hardened_csv(run)
if csv:
    st.markdown(f"Hardened baseline: `{c.file_label(csv)}`")
    b1, b2 = st.columns(2)
    if b1.button("Use this baseline in Full chain"):
        st.session_state["chain_req_path"] = str(csv)
        st.switch_page("views/3_Full_Chain.py")
    if b2.button("Use this baseline in Requirements & design"):
        # Preselect the file on the design page (its widgets read these keys when they are drawn).
        st.session_state["dsg_source"] = "File from inputs/"
        st.session_state["dsg_extra_file"] = str(csv)   # listed there even if it is outside inputs/
        st.session_state["dsg_file"] = c.file_label(csv)
        st.switch_page("views/1_Design_MUD.py")


def _show_md(path_value, missing: str) -> None:
    p = hardening.resolve(path_value)
    if not p:
        st.markdown(missing)
        return
    try:
        st.markdown(p.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        st.caption(f"Could not read `{p}`: {exc}")


paths = run.get("paths") or {}
t1, t2, t3, t4 = st.tabs(["Review packet", "Run report", "Change log", "Findings"])
with t1:
    _show_md(paths.get("review_packet"), "_No review packet_")
with t2:
    _show_md(paths.get("run_report"), "_No run report_")
with t3:
    _show_md(paths.get("change_log"), "_No change log_")
with t4:
    p = hardening.resolve(paths.get("findings"))
    if p:
        try:
            findings = json.loads(p.read_text(encoding="utf-8"))
            rows = findings if isinstance(findings, list) else findings.get("findings", [])
            st.dataframe(rows, hide_index=True, width="stretch")
        except (OSError, ValueError) as exc:
            st.caption(f"Could not read findings: {exc}")
    else:
        st.caption("No findings file.")
