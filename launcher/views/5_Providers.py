"""Providers & Keys — test each provider connection and see key status."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core.llm import get_providers, has_key, key_source, list_models, test_chat  # noqa: E402
from mudmut_core.llm import probe as probe_mod  # noqa: E402


st.title("Keys & providers")
st.caption("Keys are read from your environment (Windows user variables / .env / process) — never stored here. There is no save button; manage keys in Windows as today.")

providers = get_providers()
for pid, p in providers.items():
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.5, 2, 1.5, 1.5])
        c1.markdown(f"**{p.name}**  \n`{p.base_url}`  \nprivacy: `{p.privacy}`")
        ok = has_key(p)
        c2.markdown(f"{'✅' if ok else '❌'} key: `{key_source(p.key_env)}`")
        if c3.button("Test connection", key=f"test_{pid}"):
            with st.spinner("Testing…"):
                try:
                    models = list_models(p)
                    first = models[0]["id"] if models else ""
                    if first:
                        res, detail = test_chat(p, first)
                        st.session_state[f"test_{pid}"] = (res, detail, len(models))
                    else:
                        st.session_state[f"test_{pid}"] = (False, "no models listed", 0)
                except Exception as exc:  # noqa: BLE001
                    st.session_state[f"test_{pid}"] = (False, str(exc), 0)
        if c4.button("List models", key=f"list_{pid}"):
            with st.spinner("Fetching models…"):
                try:
                    models = list_models(p)
                    st.session_state[f"models_{pid}"] = models
                except Exception as exc:  # noqa: BLE001
                    st.session_state[f"models_{pid}"] = [{"id": f"error: {exc}", "free": False}]

        if p.is_cloud and has_key(p):
            with st.expander("🆓 Free models — probe which ones really answer"):
                st.caption("Sends only the test prompt “Say OK” (no project data) to each free model, "
                           "4 at a time. Results are cached for 24 h and shown in Workflow & Models.")
                try:
                    free_models = [m["id"] for m in list_models(p) if m.get("free")]
                except Exception as exc:  # noqa: BLE001
                    free_models = []
                    st.caption(f"Could not list models: {exc}")
                if pid == "ollama_cloud":
                    # "free" is only known after a probe, so probe the whole list.
                    try:
                        free_models = [m["id"] for m in list_models(p)]
                    except Exception:  # noqa: BLE001
                        pass
                st.write(f"{len(free_models)} model(s) to probe")
                cap = st.slider("Max models to probe", 5, 60, min(25, max(5, len(free_models))), key=f"cap_{pid}")
                if st.button("Probe free models", key=f"probe_{pid}"):
                    bar = st.progress(0.0, text="Probing…")
                    probe_mod.probe_models(
                        p, free_models, max_models=cap,
                        progress=lambda d, n: bar.progress(d / max(n, 1), text=f"Probing {d}/{n}"),
                    )
                    bar.empty()
                    st.cache_data.clear()
                known = probe_mod.cached_status(pid)
                if known:
                    counts = {}
                    for stt in known.values():
                        counts[stt] = counts.get(stt, 0) + 1
                    st.write(" · ".join(f"{probe_mod.ICONS[k]} {probe_mod.LABELS[k]}: {v}" for k, v in counts.items()))
                    st.markdown("\n".join(
                        f"- {probe_mod.ICONS[stt]} `{m}`" for m, stt in sorted(known.items(), key=lambda kv: (kv[1] != "ok", kv[0]))
                    ))

        test = st.session_state.get(f"test_{pid}")
        if test:
            res, detail, n = test
            st.write(f"{'✅' if res else '❌'} reply: `{detail}`  ({n} model(s))")
        models = st.session_state.get(f"models_{pid}")
        if models:
            st.write(" · ".join(f"`{m['id']}`{' (free)' if m.get('free') else ''}" for m in models[:20]))

st.divider()
st.info("Cloud providers (OpenRouter / NVIDIA / DeepSeek) send your requirements and designs to their servers. "
        "Every run report records which cloud providers were used.")
