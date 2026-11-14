# MUD_MUT — open, local-first, design-derived unit-test evidence for AUTOSAR

> **From architectural requirements → schema-checked draft MUD flow charts → AUTOSAR CppUTest unit tests.**
> One ASPICE-aware pipeline. Runs on **local models by default** — your requirements, designs, and code
> stay on your machine. Cloud models (Ollama Cloud, OpenRouter, NVIDIA, DeepSeek, Google) are optional, switched
> on per stage, and every run report says whether any data left the machine. One Streamlit platform, **no Docker**.
>
> **New here? Read the step-by-step guide: [docs/HOW_TO_USE.md](docs/HOW_TO_USE.md).**

**Status in five lines**

- **What it does:** requirements → Module Unit Design (MUD) spec → activity flow → C skeleton → CppUTest tests →
  build, run and coverage in WSL → requirement ↔ test trace, with a per-stage ✅/⚠️/❌ report for every run.
- **What it does not do:** it does not prove that a requirement is met, it does not replace engineering review, and
  it is not qualified or certified tooling.
- **Current result:** no requirement is verified yet by a test whose expected value comes from the requirement or
  the design. Local 8B models: **0 of 30** `verified_by_test` on the BMS sample (the AI tests mostly did not
  compile). Cloud model, AEB set: one run marks 18 of 21, but 11 of them rest only on `CHECK_TRUE(true)` tests
  and the rest on values read from the generated code. All numbers per run: [BENCHMARK.md](BENCHMARK.md).
- **Why not yet:** the generated tests take their expected values from the C code, not the design, and the trace
  also counts no-op tests. A design-derived test oracle linked to each requirement ID is the open work.
- **AI-assisted draft, not qualified tooling.** Every output needs engineer review (see `AGENTS.md`).

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-red)
![Local--first](https://img.shields.io/badge/AI-Local--first-orange)
![License](https://img.shields.io/badge/License-Apache_2.0-blue)

---

## Why this exists

ASPICE (and every serious functional-safety process) expects unit tests to be **traceable to the module/unit
design** — not written from a developer's memory of the code. In practice most teams treat that link as
paperwork and skip the design-driven step. **MUD_MUT closes that gap with local AI:** it generates the
**Module Unit Design flow charts** from requirements *and* the **unit tests** from those same designs, keeping a
requirement → design → test trace throughout.

It is built **local-first** for two reasons that are also its selling points:

- **Performance & cost** — runs offline on a single workstation/GPU; no per-token API bill.
- **Privacy** — proprietary automotive requirements and code stay on-prem, which matters under NDA/ASPICE.

A small local model on its own is not trustworthy enough for safety work — so MUD_MUT never trusts it blindly.
Every AI step is wrapped in **deterministic guardrail layers** (see [Reliability](#how-we-make-local-models-reliable)).

---

## Pipeline at a glance

> Keep this diagram current — update it in the same change whenever a stage, fallback or default model changes.

```mermaid
flowchart LR
    RAW[/"📄 inputs/requirements/<br/>DOORS · Polarion · Jira exports<br/>CSV · XLSX · ReqIF · MD · TXT"/]
    HARD["🧱 Harden requirements (optional)<br/>requirements_hardening/ · audit → author → review<br/>→ inputs/requirements_hardened/&lt;set&gt;/"]
    REQ[/"📄 requirement file<br/>raw or hardened baseline"/]
    RAW --> HARD --> REQ
    RAW --> REQ

    subgraph UI["🖥️ Streamlit (launcher/) · localhost:8501 — runs in WSL"]
        direction TB
        SET["⚙️ Keys & providers · Models · Settings<br/>preset or provider+model per stage · CppUTest folder"]
        P1["① Requirements & design<br/>step by step · background steps + cancel<br/>one run folder per component"] --- P2["② Unit tests<br/>background build · verdicts updated"] --- P3["③ Full chain<br/>first / every / named SWC · live % + stage rail<br/>cancel · reset view"]
        RR["📊 Runs & Reports<br/>stage rail · run state (interrupted / damaged)<br/>test report · coverage · trace table · ZIP"]
        AIM["🛰️ AI monitor<br/>every request / answer / thinking · test chat"]
        OCP["🤖 OpenCode Agent<br/>chat + live tool timeline"]
    end

    subgraph MUD["🧩 MUD — mud-tool library (in-process)"]
        direction TB
        IMP["Import"] --> PLAN["Plan modules (SWC)<br/><i>stage: planner</i><br/>each SWC gets only its own requirements"]
        PLAN --> SPEC["MUD spec<br/>single_pass · two_stage + review<br/><i>stages: skeleton · generator · reviewer</i>"]
        SPEC --> SCHK{"Spec check (no AI)<br/>real logic per runnable?<br/>locals read but never set · undescribed helpers"}
        SCHK -- "gaps found" --> SREP["One targeted spec repair<br/>kept only if the re-check is better"]
        SREP --> SCHK2{"no runnable with logic?"}
        SCHK -- "no gaps" --> SCHK2
        SCHK2 -- "yes" --> STOP["⛔ stop: spec rejected<br/>(activity AI never called)"]
        SCHK2 -- "no" --> ACT{"Activity flow"}
        ACT -- "quick mode / AI placeholder" --> FB["Deterministic Section 7<br/>flow builder<br/>multi-line statements joined · IDs via symbols"]
        ACT --> EXP["Export C skeleton + Mermaid"]
        FB --> EXP
    end

    subgraph C["🔧 compilable.py — gcc in WSL"]
        CMP["Declare missing symbols (TODO(design))<br/>typed by use: bit masks uint32 · value helpers float64 · libc from &lt;math.h&gt;<br/>→ comment only what still fails<br/>→ Rte stubs + &lt;SWC&gt;.h (helpers linkable by tests)<br/>quality gate: dropped logic / never-assigned / lost args = ❌"]
    end

    subgraph MUT["🧪 MUT — cpputest-rag library (in-process)"]
        direction TB
        GEN["Generate CppUTest per runnable<br/>RAG examples · <i>stage: test_generator</i>"]
        GEN --> FIX["Build (make in WSL) → fix loop:<br/>define invented constants → LLM fix ×2<br/><i>stage: test_fixer</i>"]
        FIX -- "still red" --> Q["quarantined/ (+ smoke test if none compile — reported ❌, proves nothing)"]
        FIX --> RUN["Run → JUnit · lcov coverage · HTML report"]
        Q --> RUN
    end

    OUT[/"📁 outputs/&lt;run&gt;/<br/>00_input · 01_mud · 02_code · 03_mut · 04_trace<br/>RUN_REPORT.md · run.json (verdicts, models, cloud notice)"/]

    subgraph LLM["🧠 mudmut_core/llm — one client, per-stage provider"]
        OLL[("🦙 Ollama (local)<br/>localhost:11434")]
        CLOUD[("☁️ Ollama Cloud · OpenRouter · NVIDIA · DeepSeek · Google<br/>keys from Windows user env")]
    end

    AG["🤖 opencode serve + mud-designer agent<br/>→ agentic/tools/mudmut_cli.py"]

    REQ --> IMP
    UI -.-> MUD
    EXP --> CMP --> GEN
    RUN --> OUT
    OCP --> AG -.-> MUD
    AG -.-> OUT
    RR -.-> OUT
    RS["Report server<br/>localhost:8502 · outputs/ only"] -.-> OUT
    RR -.-> RS
    AIM -.-> LLM
    SET -.-> LLM
    LLM -.-> PLAN
    LLM -.-> SPEC
    LLM -.-> GEN
```

Every run is saved in `outputs/<YYYYMMDD_HHMMSS>_<SWC>_<preset>/` with one folder per stage and a
`RUN_REPORT.md` (✅/⚠️/❌ per stage, the provider + model used for every stage, and whether any data
was sent to a cloud provider). `outputs/LATEST` names the most recent run.

## One platform, two halves

```
requirements.csv
      │
      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Streamlit platform  (launcher/)                       │
│                                                                               │
│  ① Design (MUD)                     ② Unit Tests (MUT)        ③ Full Chain   │
│  import → plan → MUD spec            C → RAG → CppUTest tests   one-click     │
│  → activity flow → C skeleton        → build/run → coverage     end-to-end    │
│  → compilability report              → requirement↔test trace                 │
│                                                                               │
│        └──────── mudmut_core/  (shared in-process engine) ────────┘           │
└──────────────────────────────────────────────────────────────────────────────┘
        │                                       │
        ▼                                       ▼
  mud-tool/  (design lib)              cpputest-rag/  (verify lib)
  Ollama on localhost:11434            C/C++ build via WSL (make/gcc/lcov)
```

| Folder | What it is | Notes |
|---|---|---|
| [`launcher/`](launcher/) | The Streamlit platform (router + `views/`: Overview · Requirements & design · Unit tests · Full chain · Runs & reports · AI monitor · Models · Keys · Settings · OpenCode agent) | `./launch.sh` / `launch.bat` |
| [`mudmut_core/`](mudmut_core/) | The shared in-process engine (design, compilable, verify, trace, report, chain, LLM providers, stage registry) | used by the UI, the CLI, the agent and the tests |
| [`mud-tool/`](mud-tool/) | Requirements → MUD spec → schema-checked draft AUTOSAR flow charts → C-skeleton export | in-process library |
| [`cpputest-rag/`](cpputest-rag/) | C code → FAISS RAG → CppUTest unit tests → build & coverage | in-process library |
| [`agentic/`](agentic/) | OpenCode agent layer (`mudmut_cli.py` tools on `mudmut_core`) | [agentic/README.md](agentic/README.md) |
| `inputs/` · `outputs/` | Requirements, guidelines, skills, test examples · one folder per run | `config/` holds presets + your stage selection |

---

## Documentation

| Document | What it covers |
|---|---|
| [docs/HOW_TO_USE.md](docs/HOW_TO_USE.md) | **Step-by-step guide to every stage and page**, reading results, troubleshooting |
| [docs/pipeline.md](docs/pipeline.md) | The stages, their outputs, re-running tests by hand, the traceability rule |
| [docs/providers.md](docs/providers.md) | Providers, free models, the probe, capping the local context window |
| [agentic/README.md](agentic/README.md) | The OpenCode agent layer |
| [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | Project background, learnings and honest limits |
| [BENCHMARK.md](BENCHMARK.md) | Every run so far: input, models, kept/stubbed C, tests compiled, verified requirements — generated from `outputs/` |

## Quick start (local, no Docker)

**Prerequisites:** [Ollama](https://ollama.com) and Linux, or **WSL (Ubuntu) on Windows**. The platform
(Python venv, Streamlit, gcc/make/CppUTest/lcov) runs inside Linux/WSL; on Windows, `setup.bat` and
`launch.bat` just start `setup.sh` / `launch.sh` in WSL, and you open http://localhost:8501 in your
Windows browser. Ollama can run natively on Windows (WSL reaches it at `localhost:11434`).

```bash
# 1. Pull the local model set (one time)
ollama pull qwen3:8b             # design / MUD generation
ollama pull qwen2.5:7b           # test generation (cpputest-rag)
ollama pull all-minilm           # test-example RAG embeddings
ollama pull nomic-embed-text     # guidelines RAG embeddings (MUD_GUIDELINES_EMBED_MODEL)

# Capped 16k-context copy used by the presets (fits an 8 GB GPU; shares the weights, no extra download)
printf 'FROM qwen3:8b\nPARAMETER num_ctx 16384\n' > /tmp/Modelfile
ollama create qwen3:8b-ctx16384 -f /tmp/Modelfile

# 2. Copy the env preset (native, localhost Ollama)
cp .env.local.example .env

# 3. One-time setup: creates .venv + installs the engine + Streamlit
./setup.sh                       # Windows: setup.bat

# 4. Install the C/C++ toolchain inside WSL (once, as root)
wsl -u root -e apt-get install -y build-essential cpputest lcov
#    (or build CppUTest yourself into Tools/cpputest-install, or set its folder on the Settings page)

# 5. Launch the platform
./launch.sh                      # Windows: launch.bat
# → opens http://localhost:8501
```

Then use the pages (details for each in [docs/HOW_TO_USE.md](docs/HOW_TO_USE.md)):

1. **Start ▸ Overview** — Ollama, the WSL build tools (incl. CppUTest) and cloud keys should be green.
   (Optional) **Design ▸ Harden requirements** turns a raw export into a reviewable, testable baseline first.
2. **Setup ▸ Settings** — CppUTest folder (empty = auto-detect), optional compiler flags; **Check** shows what was found.
3. **Setup ▸ Keys & providers** — test each provider; **Probe free models** marks which free cloud models really answer.
4. **Setup ▸ Models** — flow charts of every workflow, and a **provider + model per stage** (presets: *Local - recommended*,
   *Local - fast*, *OpenRouter - free*, *NVIDIA NIM*, *DeepSeek*, *Ollama Cloud*).
5. **Review ▸ AI monitor** — press **Quick test** in the test chat to confirm a model answers before a long run.
6. **Verify ▸ Full chain** — pick the requirements file, choose the first / every / named software component, and run
   end-to-end with a live progress bar and **Cancel**, writing `outputs/<run>/RUN_REPORT.md` per component.
   Or go step by step: **Design ▸ Requirements & design**, then **Verify ▸ Unit tests**.
7. **Review ▸ Runs & reports** — a sortable table of all runs, test report, coverage (of the component's own C file),
   run report, per-test results, ZIP download, compare runs, archive/restore.

The **current run** (newest first), a nine-box **stage rail** (green/amber/red/grey per stage; a live rail while a run is
going) and **Reset view** (clear the previous run's results from the screen; saved runs stay) are at the top of every
page.

**Honest verdicts:** a smoke-test-only result, commented-out design logic, a value that is read but never assigned, or a
helper call that lost its arguments is reported as ❌ — a compiling, "passing" run is not shown as green when the
design was not really implemented or tested. ASIL-B/C/D sets are flagged for human review.

Each run writes to `outputs/<run>/` (see below).

Prefer the CLI?

```bash
python -m mudmut_core.chain --requirements inputs/requirements/samples/bms_requirements.csv \
    --swc SWC_BatteryManagement --quick --preset local-fast
```

## Models & providers

Every pipeline stage has a **provider** (Ollama · Ollama Cloud · OpenRouter · NVIDIA NIM · DeepSeek · Google) and a
**model**. Change them on the *Models* page or apply a preset (`config/presets.json`); the current selection
persists in `config/stages.json` (gitignored). Cloud providers send your data off-machine and are recorded in every
`RUN_REPORT.md`. Free models are tagged 🆓 and can be probed (✅ answers · ⚠️ rate-limited · ❌ retired · 💲 needs
credits) — see [docs/providers.md](docs/providers.md).

API keys are read from your environment (Windows user variables such as `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`,
`DEEPSEEK_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `OLLAMA_API_KEY` / repo `.env` / process) — never written to
disk; the Keys page only ever shows "key found" / "no key".

### Outputs

```
outputs/
  LATEST                         ← name of the most recent run
  <YYYYMMDD_HHMMSS>_<SWC>_<preset>/
    RUN_REPORT.md                ← per-stage verdict ✅/⚠️/❌, models, cloud notice, timings
    run.json                     ← same, machine-readable
    llm_log.jsonl                ← every request/answer between the app and the models
    00_input/  01_mud/  02_code/  03_mut/  04_trace/
```

`03_mut/` also holds a generated `Makefile` and `build_and_run.bat` / `build_and_run.sh`: run them to recompile and
re-run the tests by hand (they use the CppUTest folder from Settings).

### What to expect from local 7B models

On an RTX 4060 (8 GB) with `qwen3:8b-ctx16384`, a quick run of the BMS sample takes about 13 minutes (the
spec stage is roughly 60 % of it); a full run with review and AI activity takes longer. Use the `-ctx16384` model variants: the plain
`qwen3:8b` loads with a 40k context, spills half onto the CPU, and is about 2× slower. Set both
`MUD_OPENAI_MODEL` and `MUD_PIPELINE_GENERATOR_MODEL` in `mud-tool/python-sidecar/.env`.

Every stage is guarded, so the chain always finishes with a truthful report rather than a fake pass:

- **Activity diagrams:** if the model's diagram is a placeholder, the deterministic Section 7 builder
  takes over and the log says so.
- **C skeleton:** symbols the MUD never defines are declared as `TODO(design)` placeholders. Only
  statements that still can't compile are commented out, as `/* TODO(design): … */`. The report states
  how many statements were kept as C.
- **Unit tests:** a fix loop first defines constants the model invented (`TODO(test)`), then asks the
  model to fix the remaining errors.
  - Test files that still don't compile are moved to `quarantined/` and listed.
  - If none compile, a deterministic smoke test runs every runnable once (clearly labelled).
  - Test failures are real results: compare them with the design before trusting either side.
- **Traceability:** a requirement is marked `verified_by_test` only when the test file of a function
  whose design carries its ID ran and every case in it passed. Otherwise it is `failing_test` (a case
  failed), `test_not_run` (the file produced no results) or `not_verified` (no test for that function).
  Known gap: a passing file of no-op cases (`CHECK_TRUE(true)`) also counts today; `BENCHMARK.md` separates them.

All output is an AI-assisted draft, not certified tooling (see `AGENTS.md`).

---

## How we make local models reliable

The moat isn't the model — it's the **guardrail layers** wrapped around it. These make a small local model's
output trustworthy enough to work with:

- **Generator ↔ Reviewer pipeline** — one local model generates, a second reviews & corrects.
- **AI reviewer pass** — coverage %, issues by section, ASIL-C/D safety & naming-convention checks.
- **Grounding** — AUTOSAR vocabulary catalog + design "skills" + RAG over your design guidelines.
- **Deterministic validators** — structural + AUTOSAR + consistency checks, Mermaid linting, JSON-schema
  validation with automatic repair/retry on low confidence.
- **Compilability guardrail** — the C skeleton is compiled with `gcc -std=c99 -fsyntax-only` in a loop; each
  statement the compiler rejects is turned into `/* TODO(design): … */`, and the kept/stubbed count is reported.
- **Test-side guardrails** — generate → compile/run → feed failures back to a model → regenerate (fix loop).
- **Provenance** — every AI output carries model id, prompt version, and a confidence score.

---

## Repository layout

```
MUD_MUT/
├── README.md                 ← you are here
├── BENCHMARK.md              ← every run's numbers (python -m mudmut_core.benchmark --write BENCHMARK.md)
├── LICENSE                   ← Apache-2.0
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── setup.sh / setup.bat      ← one-time setup (venv + deps)
├── launch.sh / launch.bat    ← launch the Streamlit platform
├── .env.example / .env.local.example / .env.auto.example
├── docs/                     ← HOW_TO_USE.md · pipeline.md · providers.md · PROJECT_OVERVIEW.md
├── Tools/                    ← optional local checkouts, e.g. a CppUTest build (git-ignored)
├── config/                   ← presets.json (tracked) · stages.json (your selection, git-ignored)
├── inputs/                   ← requirements/ (samples/) · guidelines/ · skills/ · test_examples/
├── outputs/                  ← <run>/ 00_input · 01_mud · 02_code · 03_mut · 04_trace · RUN_REPORT.md
├── launcher/
│   ├── streamlit_app.py      ← router: theme, run bar + stage rail, grouped menu
│   ├── views/                ← Overview · Design · Unit tests · Full chain · Runs & reports · AI monitor · Models · Keys · Settings · OpenCode agent
│   ├── static/vendor/        ← pinned Mermaid + svg-pan-zoom (flow charts work offline)
│   └── tests/                ← headless page tests (Streamlit AppTest), run in CI
├── mudmut_core/              ← the shared in-process engine (UI + CLI + agent + tests)
├── agentic/                  ← OpenCode agent layer (CLI tools, client, eval)
├── mud-tool/                 ← DESIGN half (history-preserved subtree)
└── cpputest-rag/             ← VERIFICATION half (history-preserved subtree)
```

---

## Security notes (read before exposing anything)

- **Localhost only.** Everything runs locally; the C/C++ build runs inside WSL. This is fine on a local dev
  machine but **must not be exposed to a network**.
- **Secrets never in git.** `.env` is ignored; ship only `*.example` files with placeholders. If you previously
  used a cloud API key locally, rotate it if there's any chance it was shared.

---

## Agentic mode (OpenCode layer)

An optional extra layer: the **OpenCode Agent** page starts `opencode serve` inside WSL and lets the
`mud-designer` agent drive the same engine through `agentic/tools/mudmut_cli.py`. Every tool call is shown
live in a timeline, permission requests can be approved inline, and the agent's run lands in
`outputs/<run>/` like any other run (visible in Runs & Reports). Needs a native OpenCode in WSL:

```bash
curl -fsSL https://opencode.ai/install | bash      # inside WSL; installs ~/.opencode/bin/opencode
```

See [agentic/README.md](agentic/README.md).

---

## License

[Apache License 2.0](LICENSE). Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
CI runs on push/PR to `main` via [.github/workflows/ci.yml](.github/workflows/ci.yml).
