# MUD_MUT — Local-AI AUTOSAR Module Unit Design → Unit Tests

> **From architectural requirements → validated MUD flow charts → AUTOSAR CppUTest unit tests.**
> One ASPICE-aligned pipeline. Runs entirely on **local 7B models** — your requirements, designs, and code
> never leave your machine. An optional cloud/API backend is available when you want it.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-green)
![Local--first](https://img.shields.io/badge/AI-Local--first%207B-orange)
![License](https://img.shields.io/badge/License-Apache_2.0-blue)

---

## Why this exists

ASPICE (and every serious functional-safety process) expects unit tests to be **traceable to the module/unit
design** — not written from a developer's memory of the code. In practice most teams treat that link as
paperwork and skip the design-driven step. **MUD_MUT closes that gap with local AI:** it generates the
**Module Unit Design flow charts** from requirements *and* the **unit tests** from those same designs, keeping a
requirement → design → test trace throughout.

It is built **local-first on 7B models** for two reasons that are also its selling points:

- **Performance & cost** — runs offline on a single workstation/GPU; no per-token API bill.
- **Privacy** — proprietary automotive requirements and code stay on-prem, which matters under NDA/ASPICE.

A small 7B model on its own is not trustworthy enough for safety work — so MUD_MUT never trusts it blindly.
Every AI step is wrapped in **deterministic guardrail layers** (see [Reliability](#how-we-make-7b-models-reliable)).

---

## The two halves (this is a monorepo)

```
requirements.csv/xlsx
        │
        ▼
┌──────────────────────────┐         C skeleton (.c)         ┌──────────────────────────┐
│   mud-tool/              │  ───────────────────────────▶   │   cpputest-rag/          │
│   DESIGN half            │   (Activity/Code-Flow diagram    │   VERIFICATION half      │
│                          │    exported as C code)           │                          │
│  requirements → MUD spec │                                  │  C code → RAG → CppUTest │
│  → UML + FLOW CHARTS     │                                  │  tests → build → coverage│
│  (Sequence/State/Class/  │                                  │                          │
│   Component/Activity)    │   ◀───────────────────────────   │                          │
│  FastAPI :8042           │      requirement→test trace      │  FastAPI :8000 / UI :3000│
└──────────────────────────┘                                  └──────────────────────────┘
              └───────────────── bridge/mud_to_tests.py ─────────────────┘
                        (glues the two + emits the traceability record)
```

| Folder | What it is | Port | Docs |
|---|---|---|---|
| [`mud-tool/`](mud-tool/) | Requirements → MUD spec → validated AUTOSAR UML **flow charts** (incl. Activity/Code-Flow) → C-skeleton export | 8042 | [mud-tool/README.md](mud-tool/README.md) |
| [`cpputest-rag/`](cpputest-rag/) | C code → FAISS RAG → CppUTest unit tests → build & coverage (LCOV/HTML/JUnit) | 8000 / 3000 | [cpputest-rag/README.md](cpputest-rag/README.md) |
| [`bridge/`](bridge/) | End-to-end glue: MUD C-skeleton → test generation → requirement-to-test traceability | — | [docs/pipeline.md](docs/pipeline.md) |

Both halves share the same stack — Python + FastAPI + Pydantic v2 + aiosqlite + **Ollama** — which is what makes
them merge cleanly into one pipeline.

---

## Quick start (100% local)

**Prerequisites:** [Ollama](https://ollama.com), Python 3.10+, Docker (for the CppUTest runner), and an NVIDIA GPU
recommended (CPU works, slower).

```bash
# 1. Pull the local 7B model set (one time)
ollama pull qwen2.5-coder:7b     # code generation
ollama pull deepseek-r1:7b       # reasoning / reviewer
ollama pull codellama:7b         # test generation (cpputest-rag)
ollama pull bge-m3               # guidelines RAG embeddings (mud-tool)
ollama pull all-minilm           # test-example RAG embeddings (cpputest-rag)
# optional: ollama pull qwen2-vl:7b   # visual QA of rendered diagrams

# 2. Copy the fully-local env preset
cp .env.local.example .env

# 3a. Design half — generate MUD flow charts
cd mud-tool/python-sidecar && pip install -e . && mudtool-server      # http://localhost:8042

# 3b. Verification half — generate & run unit tests
cd ../../cpputest-rag && docker compose up                            # http://localhost:3000
```

Or bring the whole pipeline up with the top-level compose:

```bash
docker compose up          # Ollama + mud-tool + cpputest-rag + test-runner
```

### Easiest way to launch & test — the Control Center (Streamlit)

A one-page dashboard to check service health, see which Ollama models are pulled, and run the whole
requirements → flow chart → tests pipeline with a couple of clicks:

```bash
./launch.sh        # macOS/Linux/Git-Bash   (Windows: launch.bat)
# → opens http://localhost:8501
```

It auto-creates a small venv, installs Streamlit, and starts the UI. Use the **Status** tab to confirm
mud-tool (8042), cpputest-rag (8000) and Ollama (11434) are up, then the **Run pipeline** tab to feed a C
skeleton (or a mud-tool GenerationResult) and get generated tests plus a traceability record.

Prefer the CLI? Run the bridge directly:

```bash
python bridge/mud_to_tests.py --skeleton path/to/<SWC>.c --module <SWC_Name> --run
```

---

## Choosing your backend: local vs. API

Both halves support two backends via a single toggle (`AIBackend` in `mud-tool`'s settings):

| Preset file | Mode | Meaning |
|---|---|---|
| `.env.local.example` | `LOCAL` | 100% offline, 7B models via Ollama/llama.cpp. **Default & recommended.** |
| `.env.auto.example` | `AUTO`  | Local primary, cloud API fallback for hard cases. |
| (set `MUD_AI_BACKEND=cloud`) | `CLOUD` | Anthropic / OpenAI-compatible / DeepSeek. Requires an API key. |

> ⚠️ Never commit real API keys. Only `*.example` files are tracked; `.env` is git-ignored.

---

## How we make 7B models reliable

The moat isn't the model — it's the **guardrail layers** wrapped around it. These make a small local model's
output trustworthy enough to work with:

- **Generator ↔ Reviewer pipeline** — one local model generates, a second reviews & corrects
  (`pipeline_mode: two_model`).
- **AI reviewer pass** — coverage %, issues by section, ASIL-C/D safety & naming-convention checks.
- **Visual QA** — a local vision model renders each diagram and critiques it, refining until a quality score is met.
- **Grounding** — AUTOSAR vocabulary catalog + design "skills" + RAG over your design guidelines, injected into
  every prompt so the model stays on-domain.
- **Deterministic validators** — structural + AUTOSAR + consistency checks, Mermaid linting, JSON-schema
  validation with automatic repair/retry on low confidence.
- **Provenance** — every AI output carries model id, prompt version, and a confidence score.
- **Test-side guardrails** (roadmap) — generate → compile/run in the CppUTest runner → feed failures back to a
  reviewer model → regenerate.

---

## Repository layout

```
MUD_MUT/
├── README.md                 ← you are here
├── LICENSE                   ← Apache-2.0
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── docker-compose.yml        ← one Ollama + both services + test-runner
├── .env.example              ← full variable reference
├── .env.local.example        ← 100%-offline preset
├── .env.auto.example         ← local-primary + API-fallback preset
├── docs/
│   └── pipeline.md           ← end-to-end MUD → C-skeleton → tests walkthrough
├── launcher/
│   └── streamlit_app.py      ← Control Center UI (launch & test)
├── launch.sh / launch.bat    ← one-command Control Center launch
├── .github/workflows/ci.yml  ← GitHub Actions CI
├── mud-tool/                 ← DESIGN half (history-preserved subtree)
├── cpputest-rag/             ← VERIFICATION half (history-preserved subtree)
└── bridge/
    └── mud_to_tests.py       ← the pipeline glue + traceability
```

---

## Security notes (read before exposing anything)

- **Localhost only.** `cpputest-rag`'s backend drives a CppUTest Docker container via the host Docker socket and
  runs as root to do so. This is fine on a local dev machine but **must not be exposed to a network**. See
  [cpputest-rag/README.md](cpputest-rag/README.md).
- **Secrets never in git.** `.env` is ignored; ship only `*.example` files with placeholders. If you previously
  used a cloud API key locally, rotate it if there's any chance it was shared.

---

## Publishing to GitHub

This repo is a fresh local monorepo with **no remote yet**. To publish it on GitHub:

```bash
# with the GitHub CLI (creates the repo and pushes main):
gh repo create MUD_MUT --public --source=. --remote=origin --push

# or manually, after creating an empty repo on github.com:
git remote add origin https://github.com/<you>/MUD_MUT.git
git push -u origin main
```

CI runs automatically on push/PR via [.github/workflows/ci.yml](.github/workflows/ci.yml). Your two original
GitLab repos are untouched and remain a backup.

## License

[Apache License 2.0](LICENSE). Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
