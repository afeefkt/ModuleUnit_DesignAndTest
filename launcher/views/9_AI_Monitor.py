"""AI monitor — see every request and answer between this app and the models, and chat with a model.

Two jobs: (1) watch live what each pipeline stage sent to the model and what came back
(including the model's thinking text when it returns one); (2) test a model by chatting with it
before a long run.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import agents, env  # noqa: E402
from mudmut_core.llm import get_providers, has_key, observe, probe  # noqa: E402
from mudmut_core.llm.client import stream_blocking  # noqa: E402

c.bootstrap()
st.title("AI monitor")
st.markdown("Watch every request this app sends to a model and every answer that comes back, live. "
            "Use the chat below to check that a local or cloud model really responds.")

providers = get_providers()

# ── Health ───────────────────────────────────────────────────────────────────
st.header("Is the AI reachable?")
cols = st.columns(len(providers))
for col, (pid, prov) in zip(cols, providers.items()):
    with col:
        if prov.is_local:
            n = len(c.ollama_models(env.ollama_host()))
            ok = n > 0
            st.markdown(f"**{prov.name}**  \n{'🟢 running' if ok else '🔴 not reachable'}  \n"
                        f"{n} model(s)" if ok else f"**{prov.name}**  \n🔴 not reachable")
        else:
            ok = has_key(prov)
            st.markdown(f"**{prov.name}**  \n{'🟢 key found' if ok else '⚪ no key'}")

# ── Test chat ────────────────────────────────────────────────────────────────
st.header("Test chat")


@st.cache_data(ttl=300, show_spinner=False)
def _models(provider_id: str) -> list[dict]:
    try:
        return agents.available_models(provider_id)
    except Exception:  # noqa: BLE001
        return []


cc1, cc2, cc3 = st.columns([1.2, 2.5, 1.3])
provider_id = cc1.selectbox("Provider", list(providers), format_func=lambda k: providers[k].name, key="chat_provider")
live = _models(provider_id)
status = probe.cached_status(provider_id) if provider_id != "ollama" else {}
free = {m["id"] for m in live if m.get("free") and provider_id != "ollama"}
_EMBED_HINTS = ("embed", "bge", "minilm", "nomic", "llava")   # not chat models
options = sorted((m["id"] for m in live if not any(h in m["id"].lower() for h in _EMBED_HINTS)),
                 key=lambda m: (m not in free, status.get(m) != "ok", m))
# Default to the model a pipeline stage already uses with this provider, if any.
_stage_models = [v.get("model") for v in agents.get_stages().values()
                 if (v.get("provider") or "ollama") == provider_id and v.get("model") in options]
default_index = options.index(_stage_models[0]) if _stage_models else 0
if options:
    model = cc2.selectbox(
        "Model", options, index=default_index, key=f"chat_model_{provider_id}",
        format_func=lambda m: f"{'🆓 ' if m in free else ''}{m}{(' ' + probe.ICONS[status[m]]) if m in status else ''}",
    )
else:
    model = cc2.text_input("Model id", key=f"chat_model_{provider_id}",
                           help="No model list available — check the provider's key and connection.")
max_tokens = cc3.number_input("Max answer tokens", 100, 8000, 2000, step=100,
                              help="Reasoning models spend tokens on thinking first; raise this if the answer is empty.")
system_prompt = st.text_input("System prompt (optional)", "", key="chat_system")

prov = providers[provider_id]
allowed = True
if prov.is_cloud:
    st.warning(f"Messages in this chat go to **{prov.name}** (outside this machine). "
               "Only what you type is sent — no project data.")
    allowed = st.checkbox("I understand — send my messages to this provider", key=f"chat_ok_{provider_id}")
if prov.is_cloud and not has_key(prov):
    st.error(f"No API key found for {prov.name}. Set `{prov.key_env}` as a Windows user variable and restart the app.")
    allowed = False

history = st.session_state.setdefault("chat_history", [])
top = st.columns([1, 1, 3])
if top[0].button("Quick test", disabled=not (allowed and model), help="Sends “Reply with the single word OK.”"):
    st.session_state["_chat_pending"] = "Reply with the single word OK."
if top[1].button("Clear chat"):
    st.session_state["chat_history"] = history = []

for msg in history:
    with st.chat_message(msg["role"]):
        if msg.get("thinking"):
            with st.expander("Thinking"):
                st.text(msg["thinking"])
        st.markdown(msg["content"])
        if msg.get("stats"):
            st.caption(msg["stats"])

typed = st.chat_input("Message the model…", disabled=not (allowed and model))
pending = st.session_state.pop("_chat_pending", None) or typed
if pending and allowed and model:
    history.append({"role": "user", "content": pending})
    with st.chat_message("user"):
        st.markdown(pending)
    messages = ([{"role": "system", "content": system_prompt}] if system_prompt.strip() else []) + [
        {"role": m["role"], "content": m["content"]} for m in history
    ]
    with st.chat_message("assistant"):
        think_box = st.empty()
        answer_box = st.empty()
        thinking, answer = "", ""
        started = time.monotonic()
        first = None
        try:
            for part, chunk in stream_blocking(prov, model, messages, max_tokens=int(max_tokens)):
                if first is None:
                    first = time.monotonic() - started
                if part == "reasoning":
                    thinking += chunk
                    think_box.markdown("**Thinking…**\n\n" + thinking[-1500:])
                else:
                    answer += chunk
                    answer_box.markdown(answer + "▌")
            total = time.monotonic() - started
            think_box.empty()
            if thinking:
                with st.expander("Thinking"):
                    st.text(thinking)
            answer_box.markdown(answer or "_The model returned no answer text._")
            tokens = max(1, (len(answer) + len(thinking)) // 4)   # rough: thinking tokens count too
            stats = (f"{total:.1f} s total · first token after {first or 0:.1f} s · ~{tokens} tokens "
                     f"(~{tokens / max(total, 0.1):.0f} tok/s)")
            st.caption(stats)
            if not answer.strip():
                st.warning("Empty answer. A reasoning model may have used all tokens thinking — raise "
                           "“Max answer tokens” or pick a non-reasoning model.")
            history.append({"role": "assistant", "content": answer, "thinking": thinking, "stats": stats})
        except Exception as exc:  # noqa: BLE001
            think_box.empty()
            answer_box.empty()
            st.error(f"The request failed: {exc}")
            history.pop()  # drop the unanswered user message so the chat stays consistent

# ── Live feed ────────────────────────────────────────────────────────────────
st.header("Live requests and answers")
f1, f2, f3, f4 = st.columns([1.4, 1.4, 1.2, 1])
stages = sorted({x["stage"] for x in observe.recent(300)})
stage_f = f1.selectbox("Stage", [""] + stages, format_func=lambda s: s or "All stages", key="feed_stage")
prov_f = f2.selectbox("Provider", [""] + list(providers), format_func=lambda s: providers[s].name if s else "All providers",
                      key="feed_provider")
problems = f3.toggle("Only problems", False, help="Errors and empty answers", key="feed_problems")
if f4.button("Clear list"):
    observe.clear()
calls_now = observe.recent(300)
if calls_now:
    st.download_button("Download log (JSON lines)",
                       data="\n".join(json.dumps(x, ensure_ascii=False) for x in calls_now),
                       file_name="llm_calls.jsonl", mime="application/json")


@st.fragment(run_every=1)
def _feed() -> None:
    c.ai_feed(25, stage=st.session_state.get("feed_stage", ""), provider=st.session_state.get("feed_provider", ""),
              only_problems=st.session_state.get("feed_problems", False))


_feed()
