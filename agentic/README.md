# Agentic spike — OpenCode backend + Streamlit frontend

A 1–2 day spike to answer one question: **can a local 7–9B model drive OpenCode's tool loop**
to produce a validator-clean AUTOSAR activity diagram, within a 16k context?

The agent decides; the existing deterministic `mudtool` library produces and validates every
artifact. The Streamlit platform + `mudmut_core` engine (`launcher/`, `mudmut_core/`, `bridge/`)
stays untouched as the fallback and benchmark.

```
Streamlit chat (agentic/ui/app.py)
   │  HTTP + SSE
   ▼
opencode serve (headless) ── .opencode/ (mud-designer agent + autosar-activity skill)
   │  tool calls (bash, restricted to one CLI)
   ▼
agentic/tools/mudmut_cli.py ── imports mudtool in-process (no Docker, no FastAPI)
   │
   ▼
validators gate every artifact → agentic/runs/<id>/ (requirements.json, activity.json, report, .c, .mmd)
```

## Prerequisites

- **OpenCode** on PATH (`opencode --version`). In WSL, ensure `~/.opencode/bin` precedes
  `/mnt/c/Users/<you>/AppData/Roaming/npm` in `PATH` so the Linux binary wins over the npm shim.
- **Ollama** running with the local models (`qwen3:8b-ctx16384`, `qwen3.5:9b-ctx16384`).
- **`OLLAMA_BASE_URL` must point at a reachable Ollama.** The default env value
  `http://192.168.0.1:11434/v1` is the LAN **gateway**, not the host — override it:
  ```bash
  export OLLAMA_BASE_URL=http://localhost:11434/v1
  ```
- **A Python venv with the `mudtool` deps** (the CLI imports `mudtool` in-process):
  ```bash
  python3 -m venv .venv-agentic
  .venv-agentic/bin/pip install -e mud-tool/python-sidecar pytest
  ```

## Run the agent (headless)

```bash
export OLLAMA_BASE_URL=http://localhost:11434/v1
export PATH="$(pwd)/.venv-agentic/bin:$PATH"   # so the agent's `python` has mudtool deps
opencode run --agent mud-designer \
  "Design the activity flow for RE_EstimateSOC from mud-tool/data/sample/bms_requirements.csv. Use run id 'demo'."
```

Artifacts land under `agentic/runs/demo/`: `requirements.json`, `activity.json`,
`validation_report.json`, `*.c`, `*.mmd`.

## CLI (deterministic, no LLM)

```
python agentic/tools/mudmut_cli.py import-reqs  <file>         --run <id>
python agentic/tools/mudmut_cli.py show-req    <req_id>        --run <id>
python agentic/tools/mudmut_cli.py validate-activity <activity.json> --run <id>
python agentic/tools/mudmut_cli.py export-c    <activity.json> --run <id>
python agentic/tools/mudmut_cli.py render-mermaid <activity.json> --run <id>
```

Each prints compact JSON to stdout and exits non-zero on failure. Unit tests:
`pytest agentic/tests`.

## Streamlit UI (experimental)

```bash
opencode serve --port 4096                    # headless server
streamlit run agentic/ui/app.py               # chat client (set OPENCODE_BASE_URL if not 4096)
```

The OpenCode HTTP API is experimental; `opencode_client.py` discovers endpoint paths from the
server's OpenAPI document (`/doc`) at runtime and falls back to documented defaults.

## Evaluation & go/no-go

```bash
MUDMUT_RUNS=5 python agentic/eval/run_spike.py
```

Runs `opencode run --agent mud-designer` across models × runnables, re-validates each
`activity.json` with the same CLI, and writes `agentic/eval/results.md`.

- **GO** if a local model finishes validator-clean in ≥80% of runs within 3 fix iterations,
  median under 5 minutes, no stuck loops.
- **NO-GO** — keep the CLI tools and fall back to the deterministic in-product state machine
  (narrow schema-constrained LLM calls). Nothing built here is wasted.

## Layout

```
agentic/
├── tools/mudmut_cli.py        # deterministic CLI (import/validate/export)
├── tests/test_mudmut_cli.py   # CLI unit tests
├── ui/app.py + opencode_client.py   # Streamlit chat client
├── eval/run_spike.py          # go/no-go evaluation harness
└── runs/<id>/                 # per-run artifacts (git-ignored)
.opencode/agents/mud-designer.md          # the primary agent
.opencode/skills/autosar-activity/SKILL.md # activity-JSON authoring skill
opencode.json                              # project config (least-privilege defaults)
```
