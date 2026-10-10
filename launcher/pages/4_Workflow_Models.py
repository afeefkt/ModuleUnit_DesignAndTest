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
cols = st.columns(len(presets))
for col, (pid, preset) in zip(cols, presets.items()):
    if col.button(preset.get("label", pid), key=f"preset_{pid}"):
        with st.spinner(f"Applying {pid}…"):
            agents.apply_preset(pid)
        st.rerun()
if st.button("Reset to defaults", key="reset_defaults"):
    agents.reset_defaults()
    st.rerun()

# Per-stage dropdowns
st.subheader("Stages")
if not stages:
    st.info("Could not read stage configuration.")
else:
    for key, stage in stages.items():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1.2, 2, 3])
            c1.markdown(f"**{stage['label']}**  \n`{stage['role']}` · `{stage['side']}`")
            current_provider = stage.get("provider") or "ollama"
            new_provider = c2.selectbox(
                "Provider", provider_ids,
                index=provider_ids.index(current_provider) if current_provider in provider_ids else 0,
                key=f"prov_{key}",
            )
            # Model options: live list for the provider + the current/recommended model.
            model_options = set()
            if stage.get("model"):
                model_options.add(stage["model"])
            if stage.get("recommended"):
                model_options.add(stage["recommended"])
            try:
                for m in agents.available_models(new_provider):
                    model_options.add(m["id"])
            except Exception:
                pass
            model_list = sorted(model_options)
            cur_model = stage.get("model") or ""
            default_idx = model_list.index(cur_model) if cur_model in model_list else 0
            new_model = c3.selectbox(
                "Model", model_list, index=default_idx, key=f"model_{key}",
                format_func=lambda m: f"{m} ★" if m == stage.get("recommended") else m,
            )
            if new_provider != current_provider or new_model != cur_model:
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
