"""MUD_MUT Control Center — one page to launch and test the whole pipeline.

    streamlit run launcher/streamlit_app.py

It reuses the bridge (bridge/mud_to_tests.py) for the actual work, so the UI
stays a thin orchestration layer over the same local HTTP APIs the CLI uses.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import streamlit as st

# ── Make the bridge importable ──────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "bridge"))

import mud_to_tests as bridge  # noqa: E402

DEFAULT_MUD_URL = "http://localhost:8042/api/v1"
DEFAULT_CPPUTEST_URL = "http://localhost:8000"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

st.set_page_config(page_title="MUD_MUT Control Center", page_icon="🧭", layout="wide")


# ── Small HTTP helpers (short timeouts for health) ──────────────────────────
def _ping(url: str, timeout: int = 3) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, type(exc).__name__


def _ollama_models(url: str) -> list[str]:
    try:
        data = bridge._get_json(f"{url}/api/tags", timeout=4)
        return [m.get("name", "?") for m in data.get("models", [])]
    except Exception:  # noqa: BLE001
        return []


# ── Sidebar: endpoints ──────────────────────────────────────────────────────
st.sidebar.title("🧭 MUD_MUT")
st.sidebar.caption("Local-AI AUTOSAR: requirements → flow charts → unit tests")
mud_url = st.sidebar.text_input("mud-tool API", DEFAULT_MUD_URL)
cpputest_url = st.sidebar.text_input("cpputest-rag API", DEFAULT_CPPUTEST_URL)
ollama_url = st.sidebar.text_input("Ollama", DEFAULT_OLLAMA_URL)
st.sidebar.divider()
st.sidebar.markdown(
    "- [Design UI (mud-tool)](http://localhost:8042)\n"
    "- [Test UI (cpputest-rag)](http://localhost:3000)\n"
    "- [Pipeline docs](https://github.com/) → `docs/pipeline.md`"
)

st.title("MUD_MUT Control Center")

tab_status, tab_run, tab_help = st.tabs(["① Status", "② Run pipeline", "③ Help"])

# ── Tab 1: Status ───────────────────────────────────────────────────────────
with tab_status:
    st.subheader("Service health")
    if st.button("🔄 Refresh", key="refresh_status"):
        st.rerun()

    c1, c2, c3 = st.columns(3)
    checks = [
        (c1, "mud-tool (design)", f"{mud_url}/health", "8042"),
        (c2, "cpputest-rag (verify)", f"{cpputest_url}/health", "8000"),
        (c3, "Ollama (LLM runtime)", f"{ollama_url}/api/tags", "11434"),
    ]
    _hints = {
        "8042": "mud-tool down → run `docker compose up` or:\n"
                "`cd mud-tool/python-sidecar && cp .env.local.example .env && pip install -e . && mudtool-server`",
        "8000": "cpputest-rag down → run `docker compose up` (requires Docker)",
        "11434": "Ollama down → start Ollama, then `ollama pull qwen3:8b`",
    }
    for col, label, url, port in checks:
        ok, detail = _ping(url)
        with col:
            st.metric(label, "● up" if ok else "○ down")
            st.caption(f"port {port} · {detail}")
            if not ok:
                st.info(_hints.get(port, ""), icon="ℹ️")

    st.divider()
    st.subheader("Local models pulled in Ollama")
    models = _ollama_models(ollama_url)
    if models:
        st.success(f"{len(models)} model(s) available")
        st.write(", ".join(f"`{m}`" for m in models))
    else:
        st.warning(
            "No models found (or Ollama down). Pull the local set:\n\n"
            "```\nollama pull qwen2.5-coder:7b\nollama pull deepseek-r1:7b\n"
            "ollama pull codellama:7b\nollama pull bge-m3\nollama pull all-minilm\n```"
        )

# ── Tab 2: Run pipeline ─────────────────────────────────────────────────────
with tab_run:
    st.subheader("MUD flow chart → C skeleton → CppUTest tests")
    st.caption(
        "Feed a C skeleton (exported from mud-tool) or a mud-tool GenerationResult "
        "JSON. The bridge generates tests and a requirement→test traceability record."
    )

    module = st.text_input("Module / SWC name", "SWC_Example")
    mode = st.radio(
        "Input source",
        ["Upload C skeleton (.c)", "Upload GenerationResult (.json)"],
        horizontal=True,
    )
    uploaded = st.file_uploader(
        "Drop file here",
        type=["c"] if mode.startswith("Upload C") else ["json"],
    )
    run_tests = st.checkbox("Also build + run the tests (needs Docker test-runner)")

    if st.button("▶ Run pipeline", type="primary", disabled=uploaded is None):
        if not module.strip():
            st.error("Please enter a module name.")
            st.stop()
        try:
            with st.status("Running pipeline…", expanded=True) as status:
                # Stage 1 — obtain skeleton
                if mode.startswith("Upload C"):
                    st.write("① Reading uploaded C skeleton…")
                    code = uploaded.getvalue().decode("utf-8")
                else:
                    st.write("① Exporting C skeleton from mud-tool GenerationResult…")
                    tmp = REPO_ROOT / "bridge" / "out" / f"_{module}_result.json"
                    tmp.parent.mkdir(parents=True, exist_ok=True)
                    tmp.write_bytes(uploaded.getvalue())
                    c_file = bridge.skeleton_from_result(
                        tmp, mud_url, REPO_ROOT / "bridge" / "out" / "skeletons"
                    )
                    code = c_file.read_text(encoding="utf-8")

                # Stage 2 — place into cpputest-rag
                st.write("② Placing skeleton into cpputest-rag/c_projects/…")
                bridge.place_skeleton(module, code)

                # Stage 3 — analyze + generate
                st.write("③ Analyzing + generating CppUTest tests…")
                generation = bridge.analyze_and_generate(module, cpputest_url, run_tests)

                # Stage 4 — traceability
                st.write("④ Writing traceability record…")
                out_path = REPO_ROOT / "bridge" / "out" / f"{module}_trace.json"
                bridge.write_traceability(module, code, generation, out_path)
                status.update(label="Pipeline complete ✓", state="complete")

            requirements = bridge.extract_requirements(code)
            test_files = bridge.list_test_files(generation.get("output_directory", ""))
            m1, m2, m3 = st.columns(3)
            m1.metric("Requirements traced", len(requirements))
            m2.metric("Tests generated", generation.get("tests_generated", 0))
            m3.metric("Functions analyzed", generation.get("functions_analyzed", 0))

            st.subheader("Traceability record")
            st.json(json.loads(out_path.read_text(encoding="utf-8")))
            if test_files:
                st.subheader("Generated test files")
                st.write("\n".join(f"- `{f}`" for f in test_files))
            st.caption(f"Output dir: {generation.get('output_directory', '(n/a)')}")

        except bridge.BridgeError as exc:
            st.error(f"Pipeline failed: {exc}")
        except Exception as exc:  # noqa: BLE001
            st.exception(exc)

# ── Tab 3: Help ─────────────────────────────────────────────────────────────
with tab_help:
    st.markdown(
        """
### Quick start (100% local)
1. **Pull models** (once): `qwen2.5-coder:7b`, `deepseek-r1:7b`, `codellama:7b`, `bge-m3`, `all-minilm`.
2. **Copy env preset**: `cp .env.local.example .env`
3. **Start the halves**:
   - Design:  `cd mud-tool/python-sidecar && pip install -e . && mudtool-server`  → :8042
   - Verify:  `cd cpputest-rag && docker compose up`  → :3000 / :8000
   - Or everything: `docker compose up` from the repo root.
4. **Use this page** to check status and run the end-to-end pipeline.

### Where things go
- Skeletons land in `cpputest-rag/c_projects/<module>/`
- Generated tests in `cpputest-rag/generated_tests/tests_*/`
- Traceability JSON in `bridge/out/<module>_trace.json`

See `docs/pipeline.md` for the full walkthrough.
        """
    )
