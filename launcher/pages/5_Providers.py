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

st.set_page_config(page_title="Providers & Keys", page_icon="🔑", layout="wide")

st.title("🔑 Providers & Keys")
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
