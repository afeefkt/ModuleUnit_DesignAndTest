# Agentic layer — OpenCode agent on the MUD_MUT engine

An extra, optional layer: an OpenCode agent (`mud-designer`) drives the same deterministic
engine as the Streamlit platform. The agent decides; `mudmut_core` produces and validates every
artifact, and every run lands in `outputs/<run>/` like a chain run (visible in **Runs & Reports**).

```
Streamlit page ⑦ "OpenCode Agent"  (start/stop serve, chat, live tool-call timeline)
   │  HTTP: POST /session, POST /session/{id}/prompt_async, GET /event (SSE)
   ▼
opencode serve (inside WSL) ── .opencode/agents/mud-designer.md + skills/autosar-activity
   │  bash tool, restricted to one CLI
   ▼
agentic/tools/mudmut_cli.py ── mudmut_core (design · compilable · verify · trace · report)
   ▼
outputs/<run>/  00_input · 01_mud · 02_code · 03_mut · 04_trace · RUN_REPORT.md
```

## Prerequisites

- **Native OpenCode inside WSL** (the Windows npm shim under `/mnt/c/.../npm` cannot run there):
  ```bash
  curl -fsSL https://opencode.ai/install | bash      # installs ~/.opencode/bin/opencode
  ```
  The page finds `~/.opencode/bin/opencode` even when it is not on `PATH`.
- **Providers** come from your OpenCode config (`opencode.json` / `~/.config/opencode`). API keys are
  read from environment variables (`OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, `DEEPSEEK_API_KEY`,
  `GOOGLE_GENERATIVE_AI_API_KEY`); `launch.bat` forwards them from Windows into WSL.

## Use it from the platform

1. `launch.bat` (or `./launch.sh` in WSL) → http://localhost:8501 → **OpenCode Agent**.
2. **Start serve**, pick the agent (`mud-designer`) and optionally a provider + model
   ("agent default" uses the model in `mud-designer.md`).
3. Ask, e.g. *"Design and test RE_EstimateSOC from
   inputs/requirements/samples/bms_requirements.csv. Use run id 'demo'."*
4. Watch the live timeline (each tool call with status, duration, input/output). Approve or reject
   permission requests inline. The flow chart and `RUN_REPORT.md` appear under **Artifacts**.

## CLI (deterministic, no LLM) — the agent's only tool

```
python agentic/tools/mudmut_cli.py import-reqs       <file>          --run <id>
python agentic/tools/mudmut_cli.py show-req          <req_id>        --run <id>
python agentic/tools/mudmut_cli.py validate-activity <activity.json> --run <id>
python agentic/tools/mudmut_cli.py export-c          <activity.json> --run <id>
python agentic/tools/mudmut_cli.py render-mermaid    <activity.json> --run <id>
python agentic/tools/mudmut_cli.py make-compilable   <SWC>           --run <id>
python agentic/tools/mudmut_cli.py gen-tests                         --run <id>
python agentic/tools/mudmut_cli.py build-run                         --run <id>
python agentic/tools/mudmut_cli.py trace             <SWC>           --run <id>
python agentic/tools/mudmut_cli.py report            --swc <SWC>     --run <id>
```

Each prints compact JSON and exits non-zero on failure. Run ids are sanitised (no path escape
from `outputs/`); set `MUDMUT_RUNS_DIR` to redirect (the tests use a temp dir).

## Headless / evaluation

```bash
~/.opencode/bin/opencode run --agent mud-designer "…"      # one-off run
MUDMUT_RUNS=5 python agentic/eval/run_spike.py              # models × runnables go/no-go
```

## Layout

```
agentic/
├── tools/mudmut_cli.py      # the agent's deterministic tools (on mudmut_core)
├── ui/opencode_client.py    # opencode serve client + event folding (used by launcher page 7)
├── eval/run_spike.py        # evaluation harness
└── tests/                   # CLI + event-folding tests
.opencode/agents/mud-designer.md           # the agent (least-privilege permissions)
.opencode/skills/autosar-activity/SKILL.md # activity-JSON authoring skill
opencode.json                              # project config + providers ({env:VAR} keys)
```
