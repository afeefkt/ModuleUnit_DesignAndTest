"""Shared helpers for the Streamlit launcher pages."""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mudmut_core import env, toolchain  # noqa: E402
from mudmut_core.workspace import Run  # noqa: E402


def bootstrap() -> str:
    """Configure the in-process environment and return the Ollama host."""
    return env.ollama_host()


import streamlit as _st  # noqa: E402


@_st.cache_data(ttl=120, show_spinner=False)
def _toolchain_cached():
    return toolchain.check_toolchain()


def toolchain_report():
    """WSL tool check, cached for 2 minutes (it shells into WSL; cleared by Reset view)."""
    try:
        return _toolchain_cached()
    except Exception:  # noqa: BLE001
        return None


def _get_json(url: str, timeout: int = 4):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


@_st.cache_data(ttl=20, show_spinner=False)
def ollama_models(url: str) -> list[str]:
    try:
        data = _get_json(f"{url}/api/tags", timeout=4)
        return [m.get("name", "?") for m in data.get("models", [])]
    except Exception:  # noqa: BLE001
        return []


# ── Requirement files (for pickers) ──────────────────────────────────────────
_REQ_EXT = {".csv", ".xlsx", ".reqif", ".reqifz", ".md", ".txt"}
# Side files the hardening tool writes next to a baseline — not requirement inputs.
_REQ_SKIP = ("readme", "change_log", "test_design", "trace_matrix", "_extended", "polished")


def requirement_files() -> list[Path]:
    """Requirement files under ``inputs/requirements*/`` (newest folders first, hardened ones included)."""
    out: list[Path] = []
    for base in sorted(REPO_ROOT.glob("inputs/requirements*")):
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix.lower() in _REQ_EXT and not any(s in p.name.lower() for s in _REQ_SKIP):
                out.append(p)
    return out


def file_label(p: Path) -> str:
    try:
        rel = p.relative_to(REPO_ROOT / "inputs")
    except ValueError:
        return str(p)
    tag = "  (hardened)" if rel.parts and rel.parts[0] == "requirements_hardened" else ""
    return f"{rel.as_posix()}{tag}"


# ── Reset view (clear the previous run's screen state and caches) ────────────
# Session keys owned by pages; register new page state here so Reset view clears it.
RESET_KEYS = {
    "imported", "plan", "spec_md", "module", "review", "approved", "activity", "compilability",
    "trace", "chat_history", "_chat_pending", "preset_skipped", "_chain_job_seen",
    "current_run_folder", "harden_result",
}
RESET_PREFIXES = ("test_", "models_", "map_", "trace::")
NO_RUN_KEY = "_no_run_selected"
_BAR_GEN = "_run_bar_gen"


def _bar_key() -> str:
    """Key of the run selector; a new key forces the widget to show the new value (or none)."""
    import streamlit as st
    return f"run_bar_select_{st.session_state.get(_BAR_GEN, 0)}"


def _bump_bar() -> None:
    import streamlit as st
    st.session_state[_BAR_GEN] = st.session_state.get(_BAR_GEN, 0) + 1


def reset_view() -> tuple[bool, str]:
    """Clear page state, finished jobs, the AI call list and cached lookups. Run folders are untouched.

    Returns ``(ok, message)``; refuses while a job is running.
    """
    import streamlit as st
    from mudmut_core import jobs
    from mudmut_core.llm import observe
    if jobs.any_running():
        return False, "A run is still in progress — wait for it to finish or cancel it first."
    removed = 0
    for key in list(st.session_state.keys()):
        if key in RESET_KEYS or any(str(key).startswith(p) for p in RESET_PREFIXES):
            try:
                del st.session_state[key]
                removed += 1
            except Exception:  # noqa: BLE001 - a widget key that cannot be removed now
                pass
    n_jobs = jobs.clear_finished()
    observe.clear()
    st.cache_data.clear()
    st.session_state[NO_RUN_KEY] = True   # show no run (grey rail) until one is chosen
    _bump_bar()
    return True, (f"View reset: {removed} page value(s), {n_jobs} finished job(s) and the AI call list cleared. "
                  "No run is selected now — choose one above, or start a new run. Saved runs are unchanged.")


def _reset_callback() -> None:
    import streamlit as st
    ok, msg = reset_view()
    st.session_state["_reset_msg"] = (ok, msg)


def reset_button(label: str = "Reset view", *, key: str = "reset_view", help: str | None = None) -> None:
    """A button that clears the previous run's screen state (runs on click, before the rerun)."""
    import streamlit as st
    from mudmut_core import jobs
    busy = jobs.any_running()
    st.button(label, key=key, on_click=_reset_callback, disabled=busy,
              help="Wait for the running job to finish or cancel it first." if busy else
              (help or "Clear the previous run's results, the AI call list and cached lookups from the screen. "
                        "Saved runs are not deleted."))


def show_reset_message() -> None:
    import streamlit as st
    msg = st.session_state.pop("_reset_msg", None)
    if msg:
        (st.success if msg[0] else st.warning)(msg[1])


def list_runs() -> list[Run]:
    return Run.list_runs()


def run_toolchain_install_hint() -> str:
    return toolchain.APT_INSTALL_CPPUTEST_LCOV


def render_mermaid(mmd: str, height: int = 500) -> None:
    """Render a Mermaid diagram with zoom / pan controls (CDN mermaid.js + svg-pan-zoom).

    Mouse wheel zooms, dragging pans, double-click resets; the toolbar has + / − / Fit /
    100% / Fullscreen / Download SVG. The diagram text is HTML-escaped and rendered with
    ``securityLevel:'strict'`` so LLM text (which may contain ``<``/``>`` or markup) can't
    inject HTML.

    Streamlit loads inactive tabs/expanders at width 0, which collapses Mermaid's layout
    (a 16x16 SVG), so rendering waits until the frame has a real width.
    """
    import html
    import streamlit as st
    safe = html.escape(mmd)
    box = max(height - 36, 120)
    st.components.v1.html(
        f"""
        <style>
          body {{ margin:0; font-family:sans-serif; }}
          #bar {{ display:flex; gap:4px; padding:2px 0 4px 0; }}
          #bar button {{ border:1px solid #c8c8d0; background:#f6f6fa; border-radius:4px;
                         padding:1px 8px; cursor:pointer; font-size:12px; }}
          #bar button:hover {{ background:#e6e6f0; }}
          #wrap {{ height:{box}px; border:1px solid #e3e3ea; border-radius:4px; overflow:hidden;
                   background:#fff; }}
          #wrap svg {{ width:100%; height:100%; max-width:none !important; cursor:grab; }}
          pre.mermaid {{ margin:0; height:100%; font-size:12px; white-space:pre-wrap; }}
        </style>
        <div id="bar">
          <button id="zin" title="Zoom in">+</button><button id="zout" title="Zoom out">&minus;</button>
          <button id="fit" title="Fit to window">Fit</button><button id="one" title="Actual size">100%</button>
          <button id="full" title="Fullscreen">&#x26F6;</button><button id="dl" title="Download SVG">SVG</button>
        </div>
        <div id="wrap"><pre class="mermaid">{safe}</pre></div>
        <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{ startOnLoad: false, securityLevel: 'strict',
                               flowchart: {{ useMaxWidth: false }} }});
          let pz = null;
          const render = async () => {{
            await mermaid.run({{ querySelector: '.mermaid' }});
            const svg = document.querySelector('#wrap svg');
            if (!svg || !window.svgPanZoom) return;
            svg.removeAttribute('height'); svg.removeAttribute('width');
            pz = window.svgPanZoom(svg, {{ zoomEnabled: true, panEnabled: true, fit: true, center: true,
                                          minZoom: 0.1, maxZoom: 30, dblClickZoomEnabled: false,
                                          controlIconsEnabled: false }});
            svg.addEventListener('dblclick', () => {{ pz.resize(); pz.fit(); pz.center(); }});
            const on = (id, fn) => document.getElementById(id).addEventListener('click', fn);
            on('zin', () => pz.zoomIn()); on('zout', () => pz.zoomOut());
            on('fit', () => {{ pz.resize(); pz.fit(); pz.center(); }});
            on('one', () => {{ pz.resetZoom(); pz.center(); }});
            on('full', () => {{ const el = document.documentElement;
              (document.fullscreenElement ? document.exitFullscreen() : el.requestFullscreen?.()); }});
            on('dl', () => {{
              const blob = new Blob([new XMLSerializer().serializeToString(svg)], {{ type: 'image/svg+xml' }});
              const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
              a.download = 'diagram.svg'; a.click(); URL.revokeObjectURL(a.href); }});
            document.addEventListener('fullscreenchange', () => {{
              document.getElementById('wrap').style.height =
                document.fullscreenElement ? (window.innerHeight - 40) + 'px' : '{box}px';
              pz.resize(); pz.fit(); pz.center(); }});
          }};
          let started = false;
          const timer = setInterval(() => {{
            if (!started && document.documentElement.clientWidth > 50) {{
              started = true; clearInterval(timer); render();
            }}
          }}, 250);
        </script>
        """,
        height=height,
    )


def run_picker(key: str = "run_selector"):
    """A selectbox over existing runs, keyed by run-folder name (stable)."""
    import streamlit as st
    runs = list_runs()
    if not runs:
        st.info("No runs yet — create one on the Design or Full Chain page.")
        return None
    by_name = {r.folder.name: r for r in runs}
    names = list(by_name.keys())
    chosen = st.selectbox(
        "Run", names,
        format_func=lambda n: f"{n}  ({by_name[n].swc})",
        key=key,
    )
    return by_name[chosen]


def run_latest():
    return Run.latest()


# ── Results: test report, coverage, JUnit, ZIP ───────────────────────────────
def _iframe(url: str, height: int) -> None:
    """Show a served report inline (``st.iframe`` on new Streamlit, components on old)."""
    import streamlit as st
    try:
        st.iframe(url, height=height)
    except Exception:  # noqa: BLE001 - older Streamlit
        st.components.v1.iframe(url, height=height, scrolling=True)


def results_panel(run, key: str = "results", height: int = 700) -> None:
    """Evidence of a run: headline numbers + tabs (test report, coverage, run report, JUnit).

    Reports are served by ``mudmut_core.reportserver`` (a ``file://`` link cannot be opened
    from a web page), so the inline viewer and the "open in new tab" links both work.
    """
    import streamlit as st
    from mudmut_core import reportserver, results

    mut = run.dir("mut")
    test_report = mut / "test-report.html"
    coverage_index = mut / "coverage_html" / "index.html"
    cases = results.junit_cases(mut / "test-results.xml")
    cov_all = results.coverage_summary(mut / "coverage.info")
    cov_target = results.coverage_summary(mut / "coverage.info", only=f"{run.swc}.c")
    cov = cov_target if cov_target.get("files") else cov_all

    if not (cases or cov or test_report.is_file()):
        st.info("No test results for this run yet. Generate tests and press **Rebuild & run** on the "
                "Unit tests page.")
        return

    passed = sum(1 for c in cases if c["status"] == "passed")
    failed = sum(1 for c in cases if c["status"] in ("failed", "error"))
    m1, m2, m3, m4 = st.columns(4)
    run_tests = (run.read_json("run.json") or {}).get("tests") or {}
    smoke_only = bool(run_tests.get("smoke_fallback")) or (
        bool(cases) and all(c_["group"].split(".")[-1] == "Smoke" for c_ in cases))   # classname "cpputest.Smoke"
    m1.metric("Tests passed", (f"{passed} / {len(cases)}" + (" (smoke)" if smoke_only else "")) if cases else "—",
              help="Smoke-test results only show that each runnable can be called." if smoke_only else None)
    m2.metric("Tests failed", failed if cases else "—")
    cov_help = (f"Coverage of {run.swc}.c only (test files and stubs excluded). All files: "
                f"{cov_all.get('line_pct')} % lines.") if cov is not cov_all else "Coverage of all compiled files."
    m3.metric("Line coverage", f"{cov['line_pct']} %" if cov.get("line_pct") is not None else "—", help=cov_help)
    m4.metric("Branch coverage", f"{cov['branch_pct']} %" if cov.get("branch_pct") is not None else "—",
              help=cov_help)
    quarantined = sorted(p.name for p in (mut / "quarantined").glob("*")) if (mut / "quarantined").is_dir() else []
    if quarantined:
        st.warning("Quarantined (did not compile, not counted above): " + ", ".join(quarantined))
    if smoke_only:
        st.error("No AI-written test compiled. These results come from the built-in smoke test, which calls "
                 "each runnable once and checks nothing (`CHECK(true)`). They do not verify any requirement — "
                 "coverage only shows which lines ran.")
    data = run.read_json("run.json") or {}
    for note in data.get("quality_notes") or []:
        if not note.startswith("❌ **No AI-written test"):
            st.markdown(note)

    t_report, t_cov, t_run, t_cases = st.tabs(["Test report", "Coverage", "Run report", "Test cases"])
    with t_report:
        url = reportserver.url_for(test_report) if test_report.is_file() else None
        if url:
            st.link_button("Open test report in a new tab", url)
            _iframe(url, height)
        else:
            st.caption("No test report file yet (build and run the tests first).")
    with t_cov:
        url = reportserver.url_for(coverage_index) if coverage_index.is_file() else None
        if url:
            st.link_button("Open coverage report in a new tab", url)
            _iframe(url, height)
        else:
            st.caption("No coverage report yet — it is produced by **Rebuild & run** (needs lcov in WSL).")
    with t_run:
        st.markdown(run.read_text("RUN_REPORT.md", "_No run report_"))
    with t_cases:
        if cases:
            st.dataframe(
                [{"status": {"passed": "passed", "failed": "FAILED", "error": "ERROR", "skipped": "skipped"}[c["status"]],
                  "group": c["group"], "test": c["test"], "time (s)": c["time_s"], "message": c["message"]}
                 for c in cases],
                width="stretch", hide_index=True,
            )
        else:
            st.caption("No JUnit results yet.")

    folder = results.to_windows_path(mut)
    st.caption(f"Folder: `{folder}` — re-run by hand with `build_and_run.bat` in that folder.")
    st.download_button(
        "Download this run as ZIP", data=results.zip_run(run.folder),
        file_name=f"{run.folder.name}.zip", mime="application/zip", key=f"zip_{key}",
    )


# ── Theme, run bar, stage rail, job progress ─────────────────────────────────
_THEME_CSS = """
<style>
  :root { --ink:#1D2733; --rule:#C9D1D9; --blue:#0B5FA5; --pass:#1E7B3C; --warn:#B26A00;
          --fail:#B3261E; --skip:#7A8793; --panel:#FFFFFF; }
  /* Set the face on the app root and form controls only: a blanket rule (or !important)
     would also hit Streamlit's Material icon glyphs and print their names as text. */
  .stApp, button, input, textarea, select {
    font-family: Bahnschrift, "DIN Alternate", "Segoe UI", system-ui, sans-serif; }
  [data-testid="stIconMaterial"], .material-symbols-rounded, .material-icons {
    font-family: "Material Symbols Rounded", "Material Icons" !important; }
  /* Leave room for Streamlit's fixed top header (about 3.75rem) so the run bar is not hidden under it. */
  .stMain .block-container { padding-top: 4.2rem; max-width: 1280px; }
  h1, h2, h3 { font-weight: 600; letter-spacing: 0; color: var(--ink); }
  h1 { font-size: 1.7rem; } h2 { font-size: 1.3rem; } h3 { font-size: 1.1rem; }
  p, li, .stMarkdown { font-size: 1rem; line-height: 1.5; }
  [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; font-weight: 600; }
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 4px; }
  button:focus-visible, a:focus-visible, input:focus-visible, [role="tab"]:focus-visible {
    outline: 3px solid var(--blue) !important; outline-offset: 2px; }
  .rail { display:flex; gap:3px; margin:.2rem 0 .6rem 0; flex-wrap:wrap; }
  .rail .seg { flex:1 1 90px; min-width:90px; padding:.3rem .5rem; border-radius:3px; color:#fff;
               font-size:.85rem; font-weight:600; line-height:1.2; }
  .rail .seg small { display:block; font-weight:400; opacity:.92; font-size:.75rem; }
  .rail .pass { background: var(--pass); } .rail .warn { background: var(--warn); }
  .rail .fail { background: var(--fail); } .rail .skip { background: var(--skip); }
  .rail .done { background: #3E5C76; } .rail .pending { background: #E3E8ED; color: #4A5866; }
  .rail .now { background: var(--blue); box-shadow: inset 0 -3px 0 #FFFFFF99; }
  @media (prefers-reduced-motion: no-preference) {
    .rail .now { animation: railpulse 1.6s ease-in-out infinite; } }
  @keyframes railpulse { 50% { filter: brightness(1.18); } }
  .rail-label { font-size:.85rem; color:#4A5866; margin:.4rem 0 .1rem 0; }
  .runmeta { color:#4A5866; font-size:.9rem; margin:0 0 .3rem 0; }
  .badge { display:inline-block; padding:0 .5rem; border-radius:3px; font-size:.8rem; font-weight:600;
           border:1px solid var(--rule); background:#fff; }
  .badge.cloud { border-color: var(--warn); color: var(--warn); }
  .badge.local { border-color: var(--pass); color: var(--pass); }
  .ai-card pre { white-space: pre-wrap; word-break: break-word; }
  @media print { header, [data-testid="stSidebar"], [data-testid="stToolbar"] { display:none !important; } }
</style>
"""

_STAGE_LABELS = [
    ("import", "Import"), ("plan", "Plan"), ("spec", "Spec"), ("review", "Review"),
    ("activity", "Activity"), ("compilable", "Compilable"), ("generate_tests", "Tests"),
    ("build_run", "Build & run"), ("trace", "Trace"),
]
_VERDICT = {"✅": ("pass", "✓ pass"), "⚠️": ("warn", "! partial"), "❌": ("fail", "✕ failed"), "—": ("skip", "– not run")}


def inject_theme() -> None:
    import streamlit as st
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def status_rail(run) -> None:
    """One strip of 9 segments — the verdict of each pipeline stage of ``run`` at a glance."""
    import streamlit as st
    from mudmut_core.report import effective_verdicts
    verdicts = effective_verdicts(run.read_json("run.json") or {}) if run else {}
    segs = []
    for key, label in _STAGE_LABELS:
        cls, text = _VERDICT.get(verdicts.get(key, "—"), _VERDICT["—"])
        segs.append(f'<div class="seg {cls}" title="{label}: {text}">{label}<small>{text}</small></div>')
    st.markdown('<div class="rail" role="list" aria-label="Pipeline stage results">' + "".join(segs) + "</div>",
                unsafe_allow_html=True)


_LIVE = {"done": ("done", "✓ done"), "running": ("now", "● running"), "pending": ("pending", "waiting")}


def live_rail(job) -> None:
    """The stage rail for a job that is still running: done / running now / waiting."""
    import html as _html
    import streamlit as st
    swc = ""
    if job.run_folder:
        try:
            swc = Run.load(Path(job.run_folder)).swc
        except Exception:  # noqa: BLE001
            swc = ""
    segs = []
    for key, label in _STAGE_LABELS:
        if job.quick and key == "review":
            cls, text = "pending", "skipped (quick)"
        else:
            cls, text = _LIVE[job.stage_state(key)]
        segs.append(f'<div class="seg {cls}" title="{label}: {text}">{label}<small>{text}</small></div>')
    title = f"Running now: {_html.escape(job.label)}" + (f" · {_html.escape(swc)}" if swc else "")
    st.markdown(f'<div class="rail-label">{title}</div>'
                '<div class="rail" role="list" aria-label="Stages of the running job">' + "".join(segs) + "</div>",
                unsafe_allow_html=True)


def current_run():
    """The run chosen in the run bar (session), else the newest run (by creation time)."""
    import streamlit as st
    if st.session_state.get(NO_RUN_KEY):
        return None
    runs = list_runs()
    chosen = st.session_state.get("current_run_folder")
    if chosen:
        for r in runs:
            if r.folder.name == Path(chosen).name:
                return r
    return runs[0] if runs else None


def select_run(folder: str | Path) -> None:
    """Make ``folder`` the current run on every page (safe to call before the run bar renders)."""
    import streamlit as st
    st.session_state["current_run_folder"] = str(folder)
    _bump_bar()
    st.session_state.pop(NO_RUN_KEY, None)


def _job_chip(job) -> None:
    import streamlit as st
    from mudmut_core import progress as progress_mod
    if job is None:
        return
    if job.running:
        live_rail(job)
        st.progress(job.percent / 100, text=f"{job.label} running — {job.percent} % · {job.stage} · "
                                              f"{progress_mod.fmt_duration(job.elapsed)} elapsed")
    elif job.status == "error":
        st.error(f"{job.label} stopped: {job.error}  — press **Reset view** to clear this message.")
    elif job.status == "cancelled":
        st.info(f"{job.label} was cancelled ({job.error}). The partial report is in Runs & reports.")


def run_bar() -> None:
    """Shared header: run selector, local/cloud badge, stage rail and the running-job chip."""
    import streamlit as st
    from mudmut_core import jobs
    runs = list_runs()
    if runs:
        names = [r.folder.name for r in runs]
        cleared = bool(st.session_state.get(NO_RUN_KEY))
        current = None if cleared else current_run()
        idx = None if cleared else (names.index(current.folder.name) if current else 0)
        if st.session_state.get(_bar_key()) not in names and _bar_key() in st.session_state:
            _bump_bar()   # the selected run was archived or removed
        c1, c2, c3 = st.columns([3, 2, 1.3], vertical_alignment="bottom")
        picked = c1.selectbox("Current run", names, index=idx, key=_bar_key(),
                              format_func=lambda n: n.replace("_", " ", 1),
                              placeholder="Choose a run to see its results",
                              help="Newest first. Every page shows this run.")
        with c3:
            reset_button(key="reset_view_bar")
        if picked is None:
            # After Reset view: nothing selected, so no old verdicts stay on screen.
            c2.markdown('<div class="runmeta">No run selected</div>', unsafe_allow_html=True)
            show_reset_message()
            status_rail(None)
        else:
            st.session_state.pop(NO_RUN_KEY, None)
            run = runs[names.index(picked)]
            st.session_state["current_run_folder"] = str(run.folder)
            data = run.read_json("run.json") or {}
            clouds = data.get("cloud_providers") or []
            badge = (f'<span class="badge cloud">cloud: {", ".join(clouds)}</span>' if clouds
                     else '<span class="badge local">local only</span>')
            c2.markdown(f'<div class="runmeta">{run.swc} · preset {run.preset}<br>{badge}</div>',
                        unsafe_allow_html=True)
            show_reset_message()
            status_rail(run)
    else:
        st.caption("No run yet — start on **Full chain** or **Requirements & design**.")
        show_reset_message()

    running = jobs.current()
    if running is not None:
        every = 2 if running.running else None

        @st.fragment(run_every=every)
        def _chip():
            _job_chip(jobs.current())
        _chip()


_STATUS_ICON = {"running": "⏳", "done": "✅", "empty": "⚠️", "error": "❌"}


def ai_feed(limit: int = 20, *, stage: str = "", provider: str = "", only_problems: bool = False,
            expand_running: bool = True, compact: bool = False) -> int:
    """Show recent model calls (request, thinking, response). Returns how many were shown."""
    import time as _time
    import streamlit as st
    from mudmut_core.llm import observe

    calls = observe.recent(300)
    if stage:
        calls = [x for x in calls if x["stage"] == stage]
    if provider:
        calls = [x for x in calls if x["provider"] == provider]
    if only_problems:
        calls = [x for x in calls if x["status"] in ("error", "empty")]
    calls = calls[:limit]
    if not calls:
        st.caption("No model calls recorded yet. They appear here live as soon as a stage or the test chat "
                   "talks to a model.")
        return 0
    try:
        from mudmut_core.llm import get_providers
        providers = get_providers()
    except Exception:  # noqa: BLE001
        providers = {}
    for call in calls:
        provider_id = call["provider"]
        cloud = providers[provider_id].is_cloud if provider_id in providers else False
        elapsed = (call["latency_ms"] or int((_time.time() - call["started"]) * 1000)) / 1000.0
        tps = f" · {call['tokens_per_s']} tok/s" if call.get("tokens_per_s") else ""
        toks = f" · {call['input_tokens']}→{call['output_tokens']} tokens" if call["output_tokens"] else ""
        clock = _time.strftime("%H:%M:%S", _time.localtime(call["started"]))
        title = (f"{_STATUS_ICON.get(call['status'], '•')} {clock} · {call['stage']} · "
                 f"{provider_id} / {call['model']} ({'cloud' if cloud else 'local'}) · {elapsed:.1f} s{toks}{tps}")
        if compact:
            # Side feed on a live page: title + a short tail only. Sending full prompts/thinking
            # on every refresh is what froze the browser; full detail lives on the AI monitor page.
            with st.expander(title, expanded=False):
                if call["status"] == "error":
                    st.error((call["error"] or "Request failed")[:400])
                elif call["status"] == "empty":
                    st.warning("Empty answer — a reasoning model can spend the whole token budget thinking.")
                tail = (call["response"] or call["thinking"] or "")[-600:]
                if tail:
                    st.text(tail)
            continue
        with st.expander(title, expanded=(expand_running and call["status"] == "running" and not compact)):
            if call["status"] == "error":
                st.error(call["error"] or "Request failed")
            if call["status"] == "empty":
                st.warning("The model returned an empty answer (reasoning models can spend the whole "
                           "token budget on thinking). Try a non-reasoning model or raise the token limit.")
            if call["status"] == "running":
                st.caption("Streaming… the text below is what has arrived so far."
                           if call["response"] or call["thinking"] else "Waiting for the first token…")
            if call["thinking"]:
                st.markdown("**Thinking**")
                st.code(call["thinking"][-6000:], language="text")
            elif call["status"] != "running":
                st.caption("No thinking text returned by this model.")
            if call["response"]:
                st.markdown("**Answer**")
                st.code(call["response"][-8000:], language="text")
            if not compact:
                with st.popover("Request sent"):
                    if call["system"]:
                        st.markdown("**System**")
                        st.code(call["system"][:12000], language="text")
                    st.markdown("**User**")
                    st.code((call["user"] or "")[:12000], language="text")
    return len(calls)


def job_progress_panel(job, *, height_log: int = 220) -> bool:
    """Draw a job's progress bar, stage, ETA and log. Returns True while it is still running."""
    import streamlit as st
    from mudmut_core import progress as progress_mod
    from mudmut_core import jobs as jobs_mod
    job.refresh()
    st.progress(min(job.percent, 100) / 100, text=f"{job.percent} %  ·  {job.label}")
    idx, total = job.step
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1.3])
    c1.metric("Stage", f"{job.stage or '—'} ({idx}/{total})" if job.tracker is not None else (job.stage or "—"))
    c2.metric("Elapsed", progress_mod.fmt_duration(job.elapsed))
    c3.metric("Time left (estimate)", progress_mod.fmt_duration(job.eta) if job.running else "—")
    if job.running:
        c4.button("Cancel run", key=f"cancel_{job.id}", disabled=job.cancel_requested,
                  on_click=jobs_mod.request_cancel, args=(job.id,),
                  help="Stops after the current step; the partial report is kept.")
    if job.message:
        st.caption(job.message)
    problems = [line for line in job.log if line.startswith("[error]") or " failed:" in line]
    if problems and job.running:
        st.warning(problems[-1][:400])
    if job.log:
        with st.expander("Step log", expanded=False):
            st.code("\n".join(job.log[-60:]), language="text")
    return job.running


def run_with_progress(label: str, fn, expected_seconds: float | None = None, poll: float = 0.5):
    """Run ``fn(report)`` in a background job and show a live percentage bar until it finishes.

    ``report(event)`` may be called by the work with ``{"stage", "message", "fraction": 0..1}``
    for an exact bar; otherwise the bar follows ``expected_seconds`` (an estimate, capped at 95 %).
    Returns the result or raises ``RuntimeError`` with the job's error.
    """
    import time as _time
    import streamlit as st
    from mudmut_core import jobs
    from mudmut_core import progress as progress_mod

    job = jobs.start(label, fn, track=False, expected_seconds=expected_seconds)
    bar = st.progress(0.0, text=f"{label} — starting")
    while job.running:
        job.refresh()
        eta = f" · about {progress_mod.fmt_duration(job.eta)} left" if job.eta else ""
        detail = f" · {job.message}" if job.message else ""
        bar.progress(min(job.percent, 100) / 100,
                     text=f"{label} — {job.percent} % · {progress_mod.fmt_duration(job.elapsed)} elapsed{eta}{detail}")
        _time.sleep(poll)
    bar.progress(1.0 if job.status == "done" else min(job.percent, 99) / 100,
                 text=f"{label} — {'done' if job.status == 'done' else 'stopped'} "
                      f"({progress_mod.fmt_duration(job.elapsed)})")
    if job.status == "error":
        raise RuntimeError(job.error)
    return job.result
