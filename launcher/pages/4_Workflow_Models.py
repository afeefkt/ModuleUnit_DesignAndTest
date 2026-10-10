"""Workflow & Models — flow charts of each workflow + a provider/model dropdown
per pipeline stage (the "agents")."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "launcher")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _common as c  # noqa: E402
from mudmut_core import agents  # noqa: E402
from mudmut_core.llm import get_providers  # noqa: E402

st.set_page_config(page_title="Workflow & Models", page_icon="🧠", layout="wide")

st.title("🧠 Workflow & Models")

# ── Workflow flow charts ──────────────────────────────────────────────────────
st.header("Workflows")
charts = {
    "MUD spec (two-stage)": (
        "flowchart LR\n"
        "  R[requirements] --> P{{planner}} --> SS{{skeleton}}\n"
        "  SS --> SG{{generator}} --> VAL[validate] --> ASM[assemble Markdown]\n"
        "  P --> R2[SWC + runnables]\n"
    ),
    "MUD spec review": (
        "flowchart LR\n"
        "  S[MUD spec] --> RV{{reviewer}}\n"
        "  RV -->|approved| D[done]\n"
        "  RV -->|issues| RG{{generator}} --> S\n"
    ),
    "Activity flow": (
        "flowchart LR\n"
        "  M[MUD spec §7] --> AS{{activity skeleton}}\n"
        "  AS --> AG{{activity generator}} --> AR{{activity reviewer}} --> R[repair]\n"
    ),
    "MUT test generation": (
        "flowchart LR\n"
        "  C[C skeleton] --> AN[analyze] --> EM[(embeddings)]\n"
        "  EM --> TG{{test generator}} --> BD[build]\n"
        "  BD -->|compile fail| FX{{test fixer}} --> TG\n"
        "  BD -->|ok| RN[run] --> COV[coverage]\n"
    ),
    "Full chain": (
        "flowchart LR\n"
        "  R[import] --> P[plan] --> S[spec] --> A[activity] --> C[compilable]\n"
        "  C --> T[tests] --> B[build/run] --> TR[trace] --> RP[report]\n"
    ),
}
tabs = st.tabs(list(charts.keys()))
for tab, (name, mmd) in zip(tabs, charts.items()):
    with tab:
        c.render_mermaid(mmd, height=220)

st.divider()

# ── Stage config table (provider + model dropdown per stage) ──────────────────
st.header("Agents — provider + model per stage")
st.caption("Change a provider or model here; the next run uses it. Cloud providers send your data off-machine (recorded in the run report).")

stages = agents.get_stages()
providers = get_providers()
provider_ids = list(providers.keys())

# Cloud warning banner
cloud_used = [k for k, v in stages.items() if v.get("provider") not in (None, "", "ollama")]
if cloud_used:
    st.warning(f"⚠️ Cloud providers in use: {', '.join(sorted({stages[k]['provider'] for k in cloud_used}))}. "
               "Your requirements/designs will be sent to those providers.")

# Preset buttons
presets = agents.load_presets()
st.subheader("Presets")
if presets:
    cols = st.columns(len(presets))
    for col, (pid, preset) in zip(cols, presets.items()):
        if col.button(preset.get("label", pid), key=f"preset_{pid}"):
            with st.spinner(f"Applying {pid}…"):
                _, skipped = agents.apply_preset_with_report(pid)
            if skipped:
                st.session_state["preset_skipped"] = (pid, skipped)
            st.rerun()
else:
    st.info("No presets found (config/presets.json).")
if st.session_state.get("preset_skipped"):
    pid, skipped = st.session_state.pop("preset_skipped")
    st.warning(f"Preset '{pid}' has no model for {', '.join(skipped)} — pick one below for those stages.")
if st.button("Reset to defaults", key="reset_defaults"):
    agents.reset_defaults()
    st.rerun()


@st.cache_data(ttl=300, show_spinner=False)
def _models(provider_id: str) -> list[dict]:
    """Live model list per provider, cached for 5 minutes (one call, not one per stage)."""
    try:
        return agents.available_models(provider_id)
    except Exception:
        return []


# Per-stage dropdowns
st.subheader("Stages")
if not stages:
    st.info("Could not read stage configuration.")
else:
    for key, stage in stages.items():
        spec = agents.STAGES_BY_KEY[key]
        ollama_only = spec.provider_env is None
        with st.container(border=True):
            c1, c2, c3 = st.columns([1.2, 2, 3])
            c1.markdown(f"**{stage['label']}**  \n`{stage['role']}` · `{stage['side']}`")
            shared = agents.shared_with(key)
            if shared:
                c1.caption("🔗 same setting as: " + ", ".join(stages[k]["label"] for k in shared if k in stages))
            current_provider = stage.get("provider") or "ollama"
            choices = ["ollama"] if ollama_only else provider_ids
            new_provider = c2.selectbox(
                "Provider", choices,
                index=choices.index(current_provider) if current_provider in choices else 0,
                key=f"prov_{key}", disabled=ollama_only,
                help="Ollama only for this stage" if ollama_only else None,
            )
            live = _models(new_provider)
            free = {m["id"] for m in live if m.get("free") and new_provider != "ollama"}
            model_options = {m["id"] for m in live}
            if stage.get("model") and new_provider == current_provider:
                model_options.add(stage["model"])
            if stage.get("recommended") and new_provider == "ollama":
                model_options.add(stage["recommended"])
            model_list = sorted(model_options, key=lambda m: (m not in free, m))
            cur_model = stage.get("model") or ""
            if model_list:
                new_model = c3.selectbox(
                    "Model", model_list,
                    index=model_list.index(cur_model) if cur_model in model_list else 0,
                    key=f"model_{key}_{new_provider}",
                    format_func=lambda m, rec=stage.get("recommended"), fr=free: (
                        f"{m}{' 🆓' if m in fr else ''}{' ★' if m == rec else ''}"),
                )
            else:
                new_model = c3.text_input("Model id", cur_model, key=f"model_{key}_{new_provider}",
                                          help="No model list available — check the provider key / connection.")
            if new_model and (new_provider != current_provider or new_model != cur_model):
                if st.button("Apply", key=f"apply_{key}"):
                    agents.set_stage(key, new_provider, new_model)
                    st.rerun()

# ── Key status ────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Provider keys")
for pid, p in providers.items():
    from mudmut_core.llm import has_key, key_source
    ok = has_key(p)
    st.write(f"{'✅' if ok else '❌'} **{p.name}** — key: {key_source(p.key_env)}")
