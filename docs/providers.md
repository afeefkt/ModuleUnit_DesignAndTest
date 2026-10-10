# Models & providers

Every pipeline stage has a **provider** and a **model**. Providers are the LLM
endpoints the platform can talk to; models are the specific model IDs.

## Providers

| id | base URL | key env | privacy |
|---|---|---|---|
| `ollama` | `http://localhost:11434` | — | local |
| `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | cloud |
| `nvidia` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` | cloud |
| `deepseek` | `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | cloud |

Built-ins live in `mudmut_core/llm/providers.py`; you can extend them with a
`config/providers.json` (merged over the built-ins).

## Stages (agents)

The 12 stages and their default role:

| stage | side | role |
|---|---|---|
| `planner` | mud | reasoning |
| `mud_spec_skeleton` | mud | reasoning |
| `mud_spec_generator` | mud | code |
| `mud_spec_reviewer` | mud | reasoning |
| `activity_skeleton` | mud | reasoning |
| `activity_generator` | mud | code |
| `activity_reviewer` | mud | reasoning |
| `visual_qa` | mud | vision |
| `guidelines_embed` | mud | embed (Ollama only) |
| `test_generator` | mut | code |
| `test_fixer` | mut | code |
| `rag_embed` | mut | embed (Ollama only) |

Change a stage with the *Workflow & Models* page, `config/presets.json`, or
`mudmut_core.agents.set_stage(key, provider, model)`. The current selection is
persisted in `config/stages.json` (gitignored).

## Privacy

- **Local (`ollama`)** — nothing leaves your machine.
- **Cloud (`openrouter` / `nvidia` / `deepseek`)** — your requirements, designs and
  code are sent to that provider. Every `RUN_REPORT.md` records
  `Data sent to cloud: <providers>`.

API keys are resolved from (1) the process environment, (2) the repo-root `.env`,
or (3) the Windows *User* scope when running inside WSL. They are never written
to disk, logs, `run.json`, `RUN_REPORT.md`, or `opencode.json`; the Providers page
only ever shows "✓ found" / "✗ missing".

## Free models

OpenRouter model IDs with `$0` prompt + completion pricing are flagged **free** in
the model picker, so you can try 10–30B free models on the same workflow without a
bill. Model lists are fetched live — there are no hard-coded IDs.

## Presets

- **Local – recommended** (`deepseek-r1:7b` reasoning + `qwen3:8b-ctx16384` code) — highest quality, slowest.
- **Local – fast** (`qwen2.5-coder:7b` / `qwen2.5:7b`, non-thinking) — fastest local run.
- **OpenRouter – free** / **NVIDIA** / **DeepSeek** — generation stages on the cloud provider; embeddings stay local.
