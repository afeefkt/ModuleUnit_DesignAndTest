# MUD Tool — AI-Assisted AUTOSAR Module & Unit Design

> Transform plain-text requirements into validated AUTOSAR UML diagrams in seconds, powered by Claude AI.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![License](https://img.shields.io/badge/License-Proprietary-red)

---

## What Is This?

MUD Tool automates the most tedious part of AUTOSAR software design: turning a list of requirements into proper UML diagrams (Sequence, State Machine, Class, Component, **Activity/Code-Flow**) that follow AUTOSAR naming conventions and can be imported into Modelio, Papyrus, or Enterprise Architect.

**You give it** a CSV/Excel/text file of requirements.
**It gives you** validated, AUTOSAR-compliant UML diagrams with requirement traceability — viewable instantly in a browser, VS Code, GitHub, or draw.io.

### Supported Diagram Types

| Type | What it shows | AUTOSAR use |
|------|--------------|------------|
| **Sequence** | Message flow between SWCs via RTE calls | Inter-component communication |
| **State Machine** | Mode management lifecycle, error handling | `ModeDeclarationGroup`, `OnModeSwitch` |
| **Class** | SWC structure, attributes, Runnables as operations | `ApplicationSWC` definition |
| **Component** | Port topology, SWC connections | System composition |
| **Activity / Code-Flow** | if/switch/loop logic inside Runnables, RTE read-compute-write sequences | Runnable-level code design |

---

## Hardware Requirements

MUD runs on any modern PC. The AI backend determines the minimum specs.

### With Ollama (recommended — local, free, no API key)

| Tier | RAM | GPU VRAM | Recommended Models | Diagrams/min |
|------|-----|----------|--------------------|-------------|
| **Best** | 16 GB+ | 8 GB+ (NVIDIA/AMD) | qwen2.5-coder:7b + qwen2.5:7b | ~2/min |
| **Balanced** | 12 GB | 6 GB (NVIDIA) | codellama + mistral | ~1.5/min |
| **Light** | 8 GB | 4 GB or CPU | llama3.2:3b | ~1/min |
| **Ultra-light** | 4 GB | CPU only | gemma2:2b | ~0.5/min |

> **CPU-only note:** Generation is 3–8× slower without a GPU but fully functional. Use `single_pass` pipeline mode and small models (llama3.2, gemma2:2b) for best CPU performance.

### With Anthropic Claude API (cloud)

| Component | Requirement |
|-----------|-------------|
| RAM | 4 GB minimum (Python only, no local model) |
| Internet | Required (HTTPS to api.anthropic.com) |
| API Key | From https://console.anthropic.com |

### Minimum System

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10, Linux, macOS | Windows 11, Ubuntu 22.04+ |
| Python | 3.11 | 3.12 |
| Disk | 2 GB (code only) | 10 GB (includes model files) |
| CPU | Any x86-64 or ARM64 | 4+ cores |

---

## Recommended Local AI Models

Install Ollama from https://ollama.com, then pull the models that match your hardware:

```bash
# Best quality (16 GB RAM / 8 GB VRAM) — install both
ollama pull qwen2.5-coder:7b    # Best at structured JSON / code output
ollama pull qwen2.5:7b          # Best at AUTOSAR reasoning / critique

# Balanced (12 GB RAM / 6 GB VRAM) — already installed if you followed setup
ollama pull codellama            # Code-focused generator
ollama pull mistral              # Good all-round reviewer

# Light (8 GB RAM / 4 GB VRAM)
ollama pull llama3.2             # Single model, use single_pass pipeline

# Ultra-light (4 GB RAM, CPU only)
ollama pull gemma2:2b            # 2 billion params, ~1.6 GB RAM
```

### Pipeline Configuration by Hardware Tier

Open `python-sidecar/.env` and set:

```env
# ── BEST (16 GB+ / GPU) ─────────────────────────────────────────
MUD_OPENAI_MODEL=qwen2.5-coder
MUD_PIPELINE_MODE=two_model
MUD_PIPELINE_GENERATOR_MODEL=qwen2.5-coder
MUD_PIPELINE_REVIEWER_MODEL=qwen2.5

# ── BALANCED (12 GB / 6 GB VRAM) ────────────────────────────────
MUD_OPENAI_MODEL=mistral
MUD_PIPELINE_MODE=two_model
MUD_PIPELINE_GENERATOR_MODEL=codellama
MUD_PIPELINE_REVIEWER_MODEL=mistral

# ── LIGHT (8 GB / 4 GB VRAM) ────────────────────────────────────
MUD_OPENAI_MODEL=llama3.2
MUD_PIPELINE_MODE=single_pass

# ── ULTRA-LIGHT (4 GB / CPU only) ───────────────────────────────
MUD_OPENAI_MODEL=gemma2:2b
MUD_PIPELINE_MODE=single_pass
MUD_PIPELINE_ENABLED=false
```

### Model Comparison for AUTOSAR UML Generation

| Model | Size | Strengths | Pipeline Role |
|-------|------|-----------|--------------|
| `qwen2.5-coder:7b` | 7B | Best structured JSON, code patterns | Generator |
| `qwen2.5:7b` | 7B | Best reasoning, AUTOSAR understanding | Reviewer |
| `codellama` | 7B | Good code JSON, fast | Generator |
| `mistral` | 7B | Good all-rounder, reliable | Reviewer |
| `llama3.2` | 3B | Fast, lightweight, decent quality | Single-pass |
| `gemma2:2b` | 2B | Fastest, minimal RAM, basic quality | Single-pass only |

---

## Quick Start (Windows)

```
1.  Double-click  setup.bat       ← installs everything (~3 min first time)
2.  Edit  python-sidecar\.env     ← paste your Anthropic API key
3.  Double-click  run.bat         ← starts the server
4.  Open  http://127.0.0.1:8042/ ← use the Web UI
```

No Java, no Modelio, no extra installs needed for the Web UI.

---

## Requirements

### Software
| Tool | Version | Where to get |
|------|---------|--------------|
| Python | 3.11 or newer | https://python.org/downloads |
| Ollama *(local AI)* | latest | https://ollama.com |
| Anthropic API key *(cloud AI)* | — | https://console.anthropic.com |

### Minimum Hardware (software + Ollama)
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10, Linux, macOS | Windows 11 / Ubuntu 22.04+ |
| CPU | Any x86-64 or ARM64 | 4+ cores (for faster CPU inference) |
| RAM | **8 GB** (llama3.2 single-pass) | **16 GB** (two-model pipeline) |
| Disk | 2 GB (code) + model size | 15 GB (code + qwen2.5-coder + qwen2.5) |
| GPU | Optional | NVIDIA 6 GB+ VRAM for 3–5× speed |

See **[Recommended Local AI Models](#recommended-local-ai-models)** below for per-model RAM requirements.

### Optional (Modelio plugin)
| Tool | Version |
|------|---------|
| Java JDK | 17+ |
| Maven | 3.8+ |
| Modelio | 5.4+ |

---

## Installation

### Step 1 — Run setup

**Windows:**
```bat
setup.bat
```

**Linux / macOS:**
```bash
chmod +x setup.sh && ./setup.sh
```

This will:
- Create a Python virtual environment in `python-sidecar/.venv/`
- Install all dependencies (`pip install -e ".[dev]"`)
- Copy `python-sidecar/.env.example` → `python-sidecar/.env`
- Create `data/` and `output/` directories

### Step 2 — Add your API key

Open `python-sidecar/.env` in any text editor:

```env
MUD_ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
```

> **No API key?** You can still test without one using `demo.bat` (offline mode — no AI generation, but tests all other pipeline stages).

### Step 3 — Start the server

**Windows:**
```bat
run.bat
```

**Linux / macOS:**
```bash
./run.sh
```

You should see:
```
 ------------------------------------------------
  MUD Tool Sidecar v0.1.0
  Web UI:    http://127.0.0.1:8042/
  API Docs:  http://127.0.0.1:8042/docs
  Health:    http://127.0.0.1:8042/api/v1/health
 ------------------------------------------------
```

### Step 4 — Open the Web UI

Go to **http://127.0.0.1:8042/** in any browser (Chrome, Firefox, Edge).

---

## Using the Web UI

The dashboard has three panels:

```
┌──────────────────┬──────────────────────────────┬──────────────┐
│  SIDEBAR         │  CENTER — DIAGRAM VIEWER      │  RIGHT PANEL │
│                  │                               │              │
│  1. Import       │  [Sequence] [StateMachine]    │  Validation  │
│     Upload file  │  [Class]    [Component]       │  Issues      │
│     or paste     │                               │              │
│     text         │   ┌────────────────────┐      │  Coverage    │
│                  │   │  Live Mermaid.js   │      │  Bar         │
│  Requirements    │   │  diagram renders   │      │              │
│  list (scrolls)  │   │  here              │      │  3. Export   │
│                  │   └────────────────────┘      │  Mermaid     │
│  2. Generate     │                               │  draw.io     │
│     [✓] Sequence │                               │  PlantUML    │
│     [✓] SM       │                               │  XMI         │
│     [✓] Class    │                               │  SVG         │
│     [ ] Component│                               │              │
│     [Generate]   │                               │  Source view │
└──────────────────┴──────────────────────────────┴──────────────┘
```

### Workflow

1. **Import** — Upload a `.csv`, `.xlsx`, `.txt`, or `.md` file, or paste requirements directly
2. **Generate** — Select diagram types, click **Generate** (takes 15–60 seconds depending on AI)
3. **View** — Diagrams render inline as Mermaid.js in the browser — click tabs to switch
4. **Export** — Click any export button to save files to the `output/` directory

---

## Requirement File Formats

### CSV (recommended)

```csv
Req_ID,Title,Description,Type,Priority,ASIL,Module_Hint
REQ-001,Sensor Fusion,Fuse radar and camera data,functional,must_have,ASIL-B,SWC_SensorFusion
REQ-002,Emergency Brake,Trigger braking in <100ms,safety,must_have,ASIL-D,SWC_VehicleControl
```

### Pipe-delimited text

```
REQ_ID | Type       | Description                  | Priority  | ASIL   | Module_Hint
REQ-001 | functional | Fuse radar and camera data   | must_have | ASIL-B | SWC_SensorFusion
REQ-002 | safety     | Trigger braking in <100ms    | must_have | ASIL-D | SWC_VehicleControl
```

### Markdown table

```markdown
| Req_ID  | Type       | Description                | Priority  |
|---------|------------|----------------------------|-----------|
| REQ-001 | functional | Fuse radar and camera data | must_have |
```

> **Tip:** Sample files are in `data/sample/` — try `sample_requirements.csv` first.

---

## Viewing Diagrams in Other Apps

Diagrams are exported to `output/` (or whatever directory you set in the Export panel).

| Format | How to open | Install needed? |
|--------|-------------|-----------------|
| **Web UI** (live) | `http://127.0.0.1:8042/` — any browser | Nothing |
| **`.mmd` Mermaid** | GitHub (fenced blocks), Notion, Obsidian, GitLab | Nothing |
| **`.mmd` in VS Code** | Install [Mermaid Preview](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid) extension | Free extension |
| **`.drawio`** | [diagrams.net](https://app.diagrams.net) (web, free) | Nothing |
| **`.drawio` in VS Code** | Install [draw.io integration](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio) extension | Free extension |
| **`.puml` PlantUML** | [PlantUML online](https://www.plantuml.com/plantuml/uml/) or IntelliJ plugin | Nothing |
| **`.xmi` UML 2.x** | Modelio, Papyrus, Enterprise Architect, Rhapsody | Modelio (free) |
| **`.svg` images** | Any browser, image viewer, Word, PowerPoint | Nothing |

---

## Export Formats Explained

### Mermaid (`.mmd`) — Best for GitHub/Docs
Text-based diagrams that render natively in GitHub README files, Notion pages, Obsidian notes, and GitLab wikis. No install required.

```
output/
├── sequence_SWC_SensorFusion.mmd
├── state_machine_SWC_VehicleControl.mmd
└── class_SWC_SafetyMonitor.mmd
```

### draw.io (`.drawio`) — Best for Editing
Fully editable diagram files. Drag into [app.diagrams.net](https://app.diagrams.net) to edit, annotate, and export to PDF/PNG.

### SVG/PNG — Best for Reports
Rendered image files via [Kroki.io](https://kroki.io) (free public service). Ready to embed in Word, PowerPoint, Confluence, etc. Requires internet.

### XMI (`.xmi`) — Best for Model Tools
UML 2.x XMI format for importing into full-featured UML tools (Modelio, Papyrus, IBM Rhapsody, Sparx EA).

### PlantUML (`.puml`) — Best for Git Diffs
Git-friendly text format. Human-readable, easy to diff in PRs.

---

## AI Backend Options

### Default: Anthropic Claude (Cloud)

Set in `.env`:
```env
MUD_AI_BACKEND=cloud
MUD_CLOUD_PROVIDER=anthropic
MUD_ANTHROPIC_API_KEY=sk-ant-...
MUD_ANTHROPIC_MODEL=claude-sonnet-4-5-20250514
```

### Alternative: OpenAI / Any OpenAI-compatible API

```env
MUD_AI_BACKEND=cloud
MUD_CLOUD_PROVIDER=openai_compatible
MUD_OPENAI_API_KEY=sk-...
MUD_OPENAI_BASE_URL=https://api.openai.com/v1
MUD_OPENAI_MODEL=gpt-4o
```

### Local LLM (Offline, no API key)

Requires a GGUF model file (e.g., from HuggingFace):
```env
MUD_AI_BACKEND=local
MUD_LOCAL_MODEL_PATH=C:\models\mistral-7b-instruct.gguf
MUD_LOCAL_MODEL_N_GPU_LAYERS=-1
```

Install the local LLM dependency:
```bat
cd python-sidecar
.venv\Scripts\pip install -e ".[local-llm]"
```

---

## Configuration Reference

All settings use the `MUD_` prefix and can be set in `python-sidecar/.env` or as environment variables.

| Variable | Default | Description |
|----------|---------|-------------|
| `MUD_HOST` | `127.0.0.1` | Server bind address |
| `MUD_PORT` | `8042` | Server port |
| `MUD_DEBUG` | `false` | Enable hot-reload |
| `MUD_LOG_LEVEL` | `info` | Logging level (`debug`/`info`/`warning`) |
| `MUD_AI_BACKEND` | `cloud` | `cloud`, `local`, or `auto` |
| `MUD_ANTHROPIC_API_KEY` | — | **Required for cloud AI** |
| `MUD_ANTHROPIC_MODEL` | `claude-sonnet-4-5-20250514` | Claude model to use |
| `MUD_LOCAL_MODEL_PATH` | — | Path to `.gguf` model file |
| `MUD_LOCAL_MODEL_AUTO_GPU` | `true` | Auto-detect CUDA/Metal GPU; `false` to use `N_GPU_LAYERS` override |
| `MUD_CONFIDENCE_THRESHOLD` | `0.6` | Minimum AI confidence to accept output |
| `MUD_MAX_RETRIES` | `3` | AI generation retry count |
| `MUD_USE_KROKI` | `true` | Enable SVG/PNG rendering via Kroki.io |
| `MUD_KROKI_BASE_URL` | `https://kroki.io` | Kroki.io server (use local instance if needed) |
| `MUD_PLANTUML_JAR_PATH` | — | Path to `plantuml.jar` for offline rendering |
| `MUD_VALIDATION_STRICT_MODE` | `false` | Fail on warnings as well as errors |

---

## REST API

The sidecar exposes a full REST API at `http://127.0.0.1:8042/api/v1/`. Interactive docs at `http://127.0.0.1:8042/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Server health + AI backend status |
| `GET` | `/config` | Current (non-sensitive) config |
| `POST` | `/requirements/import` | Upload file (multipart) |
| `POST` | `/requirements/import/text` | Paste raw text |
| `POST` | `/analyze` | AI requirement clustering (Stage 2) |
| `POST` | `/generate` | **Main endpoint** — AI diagram generation |
| `POST` | `/validate` | Validate existing generation result |
| `POST` | `/export` | Export to `xmi`, `plantuml`, `mermaid`, `drawio` |
| `POST` | `/export/mermaid/inline` | Get Mermaid text inline (used by Web UI) |
| `POST` | `/render` | Render to SVG/PNG via Kroki.io |
| `GET` | `/traceability` | Full traceability matrix + coverage |
| `GET` | `/traceability/requirement/{id}` | Traces for one requirement |
| `POST` | `/traceability/accept` | Mark element as human-reviewed |

---

## AUTOSAR Conventions

The tool enforces AUTOSAR naming conventions automatically:

| Element | Pattern | Example |
|---------|---------|---------|
| SWC | `SWC_PascalCase` | `SWC_SensorFusion` |
| Runnable | `RE_PascalCase` | `RE_FuseSensorData` |
| Provided Port | `PP_PascalCase` | `PP_FusedData` |
| Required Port | `RP_PascalCase` | `RP_RadarInput` |

Violations are flagged as `AUT-006` warnings in the validation report. Override the regex patterns via `.env` if your project uses different conventions.

### Validation Rules

| Rule ID | Category | Description |
|---------|----------|-------------|
| `STR-001` to `STR-015` | Structural | Lifeline IDs, orphan detection, state count |
| `AUT-001` to `AUT-010` | AUTOSAR | Port direction, runnable triggers, naming, coverage |
| `CON-001` to `CON-005` | Consistency | Cross-diagram element matching |

---

## Running Tests

```bat
run_tests.bat
```

Or directly:
```bat
cd python-sidecar
.venv\Scripts\pytest tests/ -v --tb=short
```

---

## Offline Demo (No API Key)

Tests the full pipeline except AI generation — useful for verifying the install:

```bat
demo.bat
```

This will:
1. Import `data/sample/sample_requirements.csv`
2. Run validation
3. Export PlantUML `.puml` files to `output/demo/`
4. Export XMI `.xmi` file to `output/demo/`
5. Show traceability coverage report

---

## Optional: Modelio Plugin

For teams using Modelio as their primary UML tool, the Java plugin provides a native IDE integration with the same AI backend.

### Prerequisites
- Java JDK 17+
- Apache Maven 3.8+
- Modelio 5.4+

### Build

```bat
cd modelio-plugin
mvn clean package
```

### Install in Modelio
1. Open Modelio → **Configuration → Modules**
2. Click **Add** → select `modelio-plugin/target/mudtool-plugin-*.jmdac`
3. The **MUD Tool** menu appears in the toolbar

### Configuration
Edit `modelio-plugin/src/main/resources/mudtool.properties`:
```properties
mudtool.sidecar.url=http://127.0.0.1:8042
mudtool.sidecar.timeout=120
```

> The Python sidecar must be running (`run.bat`) before using the Modelio plugin.

---

## Project Structure

```
MUD/
├── python-sidecar/              # Python FastAPI AI backend
│   ├── src/mudtool/
│   │   ├── ai/                  # AI backends (Anthropic, OpenAI, local LLM)
│   │   ├── api/                 # REST API routes + dependency injection
│   │   ├── config/              # Settings (pydantic-settings)
│   │   ├── generator/           # Exporters: XMI, PlantUML, Mermaid, draw.io, SVG
│   │   ├── importers/           # CSV, Excel, TXT, Markdown parsers
│   │   ├── models/              # Pydantic data models (AUTOSAR, UML, requirements)
│   │   ├── traceability/        # SQLite requirement-to-model trace store
│   │   ├── validation/          # 3-pass validator (structural + AUTOSAR + consistency)
│   │   └── web/                 # Built-in browser dashboard
│   ├── prompts/                 # YAML prompt templates (per diagram type)
│   ├── tests/                   # Pytest unit tests
│   └── pyproject.toml
│
├── modelio-plugin/              # Java Modelio plugin (optional)
│   └── src/main/java/com/mudtool/
│
├── common/
│   └── schemas/json_uml_schema.json   # JSON Schema for AI interchange format
│
├── data/sample/                 # Sample requirements (ADAS + EPS ASIL-D)
│   ├── sample_requirements.csv  # ADAS sensor fusion (15 reqs — quick demo)
│   └── eps_requirements.csv     # EPS ASIL-D (55 reqs — full activity diagram demo)
│
├── setup.bat / setup.sh         # First-time install
├── run.bat   / run.sh           # Start server
├── run_tests.bat / run_tests.sh # Run test suite
└── demo.bat                     # Offline demo (no API key)
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'mudtool'`
You haven't installed the package yet. Run `setup.bat` first.

### Server starts but Web UI shows "AI: offline"
Check `python-sidecar/.env` — make sure `MUD_ANTHROPIC_API_KEY` is set and valid.

### `pip is taking a long time` during setup
This is normal during dependency resolution. Wait 3–5 minutes. If it exceeds 10 minutes, press Ctrl+C and run:
```bat
cd python-sidecar
.venv\Scripts\pip install -e . --no-deps
.venv\Scripts\pip install fastapi uvicorn[standard] pydantic pydantic-settings openpyxl anthropic httpx python-multipart pyyaml aiosqlite lxml jinja2
```

### Port 8042 already in use
Change the port in `.env`:
```env
MUD_PORT=9000
```

### Generation returns empty diagrams
- Check AI backend is reachable: `http://127.0.0.1:8042/api/v1/health`
- Lower the confidence threshold: `MUD_CONFIDENCE_THRESHOLD=0.4`
- Check logs in the terminal running `run.bat`

### SVG export fails
SVG/PNG rendering uses [Kroki.io](https://kroki.io) (requires internet). For offline rendering, download `plantuml.jar` and set:
```env
MUD_USE_KROKI=false
MUD_PLANTUML_JAR_PATH=C:\tools\plantuml.jar
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Client (Browser / Modelio / curl)                          │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP REST  (port 8042)
┌────────────────────────▼────────────────────────────────────┐
│  Python FastAPI Sidecar                                      │
│                                                              │
│  Stage 1 — Import                                            │
│    CSV / Excel / TXT / Markdown  →  RequirementSet           │
│                                                              │
│  Stage 2 — AI Generation Pipeline                            │
│    ┌──────────────────────────────────────────────────────┐  │
│    │  single_pass: one model → draft                      │  │
│    │  two_model:   Generator → Draft → Reviewer Critique  │  │
│    │               → Refiner → Final (best quality)       │  │
│    │                                                      │  │
│    │  Diagrams: Sequence │ StateMachine │ Class           │  │
│    │            Component │ Activity/CodeFlow (new)       │  │
│    └──────────────────────────────────────────────────────┘  │
│                                                              │
│  Stage 3 — AUTOSAR Mapping (naming + port typing)            │
│                                                              │
│  Stage 4 — Validation (STR + AUT + CON rules)                │
│                                                              │
│  Stage 5 — Export                                            │
│    XMI │ PlantUML │ Mermaid (.mmd) │ draw.io (.drawio) │ SVG │
│                                                              │
│  Traceability Store (SQLite — req → model element links)     │
└────────────────────────┬────────────────────────────────────┘
                         │ optional
┌────────────────────────▼────────────────────────────────────┐
│  Modelio Java Plugin (optional native IDE integration)       │
└─────────────────────────────────────────────────────────────┘
```

### AI Backend Options

```
Ollama (local, free)         Anthropic Claude (cloud)
  qwen2.5-coder ←generator    claude-sonnet-4-6
  qwen2.5       ←reviewer
  codellama, mistral
  llama3.2, gemma2:2b
        │                              │
        └──────────────┬───────────────┘
                       │
            MUD Orchestrator
          (prompt engine + retry
           + JSON parsing + validation)
```

### GPU Auto-Detection (local llama.cpp backend)

When `MUD_LOCAL_MODEL_AUTO_GPU=true` (default):
- **NVIDIA GPU found** → `n_gpu_layers = -1` (all layers on GPU — maximum speed)
- **No GPU detected** → `n_gpu_layers = 0` (CPU-only mode — no VRAM needed)

Override: set `MUD_LOCAL_MODEL_N_GPU_LAYERS=N` (0 = CPU, -1 = all GPU, N = N layers on GPU)

> Ollama handles GPU detection internally — this setting only applies to the built-in llama.cpp backend (`MUD_AI_BACKEND=local`).

---

## License

Proprietary. All rights reserved.
