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
| `google` | `https://generativelanguage.googleapis.com/v1beta/openai` | `GOOGLE_GENERATIVE_AI_API_KEY` | cloud |
| `ollama_cloud` | `https://ollama.com/v1` | `OLLAMA_API_KEY` | cloud (Ollama's hosted models — separate from your local Ollama) |

### Free models

The 🆓 tag means a different thing per provider:

| provider | "free" means |
|---|---|
| `openrouter` | price 0 (the `:free` models; shared upstream rate limits, so some answer 429) |
| `nvidia` | NIM trial credits — every hosted chat model, rate-limited (many catalogue entries are retired and answer 404) |
| `ollama_cloud` | on the free plan (usage-limited). Not every listed model is: others answer 402 "needs credits", so 🆓 is only shown after a probe saw the model answer |

Lists are long and partly stale, so the **Providers** page has **Probe free models**: it sends
only the test prompt "Say OK" (no project data) to each model, 4 at a time, and caches the result
for 24 h in `config/model_probe.json`. **Workflow & Models** then marks each model
✅ answers · ⚠️ rate-limited / empty reply (reasoning models) · ❌ not hosted · 💲 needs credits,
and has a **Free models only** toggle and a filter box. Presets with a blank cloud model
(`openrouter-free`, `nvidia`, `ollama-cloud`) pick the first probed ✅ non-reasoning model.

The Ollama Cloud key is the Windows user variable `OLLAMA_API_KEY` (forwarded into WSL by
`launch.bat`; never written to a file).

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

## Local models: cap the context window (8 GB GPUs)

Ollama loads a model with its full native context unless told otherwise — `deepseek-r1:7b` loads
**131k tokens** (~12 GB), which spills onto the CPU, runs slowly and can stall Ollama when it swaps
models. Use capped variants for pipeline stages (the `-ctx16384` models). To make one:

```bash
printf 'FROM deepseek-r1:7b\nPARAMETER num_ctx 16384\n' > /tmp/Modelfile
ollama create deepseek-r1:7b-ctx16384 -f /tmp/Modelfile     # shares the weights, no extra download
```

Then pick it on *Workflow & Models*. The **Local – recommended** preset uses one capped model
(`qwen3:8b-ctx16384`) for every MUD stage, so Ollama never swaps models mid-design; the chain unloads
it before test generation.
