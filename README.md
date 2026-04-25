# MUD Tool — AI-Assisted AUTOSAR Module & Unit Design

> From raw architectural requirements to validated AUTOSAR UML diagrams — with an AI-driven Module Planning and MUD Specification stage before diagram generation.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)
![License](https://img.shields.io/badge/License-Proprietary-red)

---

## What Is This?

MUD Tool automates the most tedious part of AUTOSAR software design: turning a list of architectural requirements into structured Module Unit Design specs and proper UML diagrams (Sequence, State Machine, Class, Component, **Activity/Code-Flow**) that follow AUTOSAR naming conventions and can be imported into Modelio, Papyrus, or Enterprise Architect.

**You give it** a CSV/Excel/text file of requirements.  
**It gives you:**
1. A **module decomposition** — AI detects every SWC with ASIL level, runnables, ports, and CalPrm
2. A **detailed MUD Spec Markdown** — ports, data types, signal ranges, IRVs, ExclusiveAreas, CalPrm, runnable descriptions — for the module you choose
3. An **AI reviewer pass** — coverage score, issues by section, suggestions
4. **Validated AUTOSAR UML diagrams** for that module with requirement traceability

---

## Enhanced Workflow — 5 Stages

```
┌──────────────────────────────────────────────────────────────────────┐
│                     MUD TOOL ENHANCED WORKFLOW                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Stage 1 ─ Import                                                    │
│    CSV / Excel / TXT / Markdown  ──►  RequirementSet                 │
│                                                                      │
│  Stage 1.5 ─ Elaborate (optional)                                    │
│    AI pre-analysis: extract SWCs, ports, timing, ASIL               │
│    Enriches context for all downstream stages                        │
│                                                                      │
│  Stage 1.75 ─ Module Planning  ◄── NEW                               │
│    AI analyses ALL requirements and detects module decomposition     │
│    Returns: swc_name, asil, runnables[], req_ids[], complexity       │
│    UI shows module cards ── user selects ONE module                  │
│                                                                      │
│  Stage 2 ─ MUD Spec Generation  ◄── NEW                              │
│    AI generates detailed Markdown spec for the SELECTED module only  │
│    Covers: P-Ports, R-Ports, CalPrm, Runnables, IRVs,               │
│            ExclusiveAreas, Data Types, Safety (DEM), Functional desc │
│                                                                      │
│  Stage 2b ─ AI Reviewer Pass  ◄── NEW                                │
│    Independent AI review: coverage%, issues by section,              │
│    ASIL-C/D safety checks, naming convention compliance              │
│    Returns: approved / needs revision + issue list                   │
│                                                                      │
│  Stage 3 ─ Diagram Generation                                        │
│    Focused on the selected module + MUD Spec as context              │
│    Pipeline modes: single_pass │ multi_pass │ two_model_fast         │
│                    │ two_model (generator+reviewer — best quality)   │
│    Diagram types:  Sequence │ State Machine │ Class │ Component      │
│                    │ Activity/Code-Flow                              │
│                                                                      │
│  Stage 4 ─ Validation + Traceability                                 │
│    STR (structural) + AUT (AUTOSAR) + CON (consistency) rules        │
│    Requirement-to-model element traceability matrix                  │
│                                                                      │
│  Stage 5 ─ Export                                                    │
│    MUD Spec .md │ Mermaid .mmd │ draw.io .drawio │ PlantUML .puml   │
│    XMI (UML 2.x) │ SVG/PNG images │ C-Code Skeleton                 │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Supported Diagram Types

| Type | What it shows | AUTOSAR use |
|------|--------------|-------------|
| **Sequence** | RTE message flows between SWCs (Rte_Read/Write/Call/Result, IRV self-messages) | Inter-component communication |
| **State Machine** | Mode management lifecycle, error/safety degradation | `ModeDeclarationGroup`, `OnModeSwitch`, SAFE_STATE |
| **Class** | SWC structure: runnables, IRVs, CalPrm, ExclusiveAreas | `ApplicationSWC` definition |
| **Component** | Port topology, SWC connections, ASIL annotations | System composition |
| **Activity / Code-Flow** | if/switch/loop logic inside runnables, RTE read-compute-write sequences | Runnable-level code design |

---

## AUTOSAR Design Patterns Supported

The AI understands and generates the following AUTOSAR-specific patterns:

| Pattern | What it is | Where generated |
|---------|-----------|-----------------|
| **IRV (Inter-Runnable Variable)** | Typed data shared between runnables inside one SWC; accessed via `Rte_IrvRead/Rte_IrvWrite` | Class diagram (private attr), Sequence diagram (self-message) |
| **ExclusiveArea** | Mutex protecting an IRV when accessed from runnables in different OS tasks; `Rte_Enter_<EA>()/Rte_Exit_<EA>()` | Class diagram (description field), Sequence diagram (bracketed self-messages) |
| **CalPrm** | Tunable constant accessed via `Rte_CData_<Name>()`; gains, thresholds, lookup tables | Class diagram (constant-visibility attr), Component diagram (RP_ parameter port) |
| **SAFE_STATE** | ASIL-C/D required state; freezes outputs, calls `Dem_SetEventStatus(DTC_xxx, DEM_EVENT_STATUS_FAILED)` | State Machine diagram (mandatory for ASIL-C/D) |
| **Mode Switch** | `Rte_Switch(PP_ModeSwitchPort, MODE_NAME)` as transition action | State Machine diagram |
| **Sender-Receiver (SR)** | Async data exchange via `Rte_Write(PP_...)/Rte_Read(RP_...)` | Sequence + Component |
| **Client-Server (CS)** | Sync calls via `Rte_Call(RP_.../Rte_Result(RP_...)` | Sequence + Component |
| **Safety degradation** | `NORMAL → DEGRADED → SAFE_STATE → LIMP_HOME` | State Machine |

---

## Hardware Requirements

### With Ollama (recommended — local, free, no API key)

| Tier | RAM | GPU VRAM | Recommended Models | Diagrams/min |
|------|-----|----------|--------------------|-------------|
| **Best** | 16 GB+ | 8 GB+ (NVIDIA/AMD) | qwen2.5-coder:7b + qwen2.5:7b | ~2/min |
| **Balanced** | 12 GB | 6 GB (NVIDIA) | codellama + mistral | ~1.5/min |
| **Light** | 8 GB | 4 GB or CPU | llama3.2:3b | ~1/min |
| **Ultra-light** | 4 GB | CPU only | gemma2:2b | ~0.5/min |

> **CPU-only note:** Generation is 3–8× slower without a GPU but fully functional. Use `single_pass` pipeline mode and small models for best CPU performance.

### With Anthropic Claude API (cloud)

| Component | Requirement |
|-----------|-------------|
| RAM | 4 GB minimum (Python only, no local model) |
| Internet | Required (HTTPS to api.anthropic.com) |
| API Key | From https://console.anthropic.com |

---

## Recommended Local AI Models

```bash
# Best quality (16 GB RAM / 8 GB VRAM)
ollama pull qwen2.5-coder:7b    # Best at structured JSON / code output
ollama pull qwen2.5:7b          # Best at AUTOSAR reasoning / critique

# Balanced (12 GB RAM / 6 GB VRAM)
ollama pull codellama            # Code-focused generator
ollama pull mistral              # Good all-round reviewer

# Light (8 GB RAM / 4 GB VRAM)
ollama pull llama3.2             # Single model, use single_pass pipeline

# Ultra-light (4 GB RAM, CPU only)
ollama pull gemma2:2b            # 2 billion params, ~1.6 GB RAM
```

### Pipeline Configuration by Hardware Tier

Open `python-sidecar/.env`:

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

---

## Quick Start (Windows)

```
1.  Double-click  setup.bat       ← installs everything (~3 min first time)
2.  Edit  python-sidecar\.env     ← paste your Anthropic/Ollama config
3.  Double-click  run.bat         ← starts the server
4.  Open  http://127.0.0.1:8042/ ← use the Web UI
```

---

## Using the Web UI

```
┌────────────────────┬────────────────────────────────────┬──────────────┐
│  SIDEBAR           │  CENTER PANEL (switches per stage) │  RIGHT PANEL │
│                    │                                    │              │
│  1 - Import        │  [Module Picker]  ─── Stage 1.75  │  Validation  │
│    Upload / paste  │   ┌─────────────────────────────┐ │  Issues      │
│                    │   │ SWC_SensorFusion [ASIL-B]   │ │              │
│  Requirements list │   │ SWC_VehicleControl [ASIL-D] │ │  Traceability│
│                    │   │ SWC_SafetyMonitor [ASIL-D]  │ │  Coverage    │
│  1.5 - Elaborate   │   └─────────────────────────────┘ │              │
│    AI pre-analysis │         ↓ select + confirm         │  AI Reasoning│
│                    │                                    │              │
│  1.75 - Analyse    │  [MUD Spec Viewer] ─── Stage 2    │  Design      │
│  Modules           │   ┌─────────────────────────────┐ │  Guidelines  │
│    [Plan Modules]  │   │  # MUD Spec: SWC_SensorF... │ │              │
│                    │   │  ## 2. Ports                 │ │  4 - Export  │
│  2 - MUD Spec      │   │  | Port | Interface | ...    │ │  MUD Spec.md │
│    Module: ▼       │   │  ## 3. Runnables             │ │  Mermaid     │
│    [Generate Spec] │   │  ...                         │ │  draw.io     │
│    [AI Review]     │   └─────────────────────────────┘ │  PlantUML    │
│                    │         ↓ Use for Diagrams →       │  XMI         │
│  3 - Generate      │                                    │  SVG         │
│    Pipeline: ▼     │  [Diagram Viewer] ──── Stage 3    │  C-Skeleton  │
│    [✓] Sequence    │   ┌─────────────────────────────┐ │              │
│    [✓] SM          │   │ Mermaid.js renders live     │ │              │
│    [✓] Class       │   │  [Seq] [SM] [Class] [Flow]  │ │              │
│    [ ] Component   │   └─────────────────────────────┘ │              │
│    [Generate]      │                                    │              │
└────────────────────┴────────────────────────────────────┴──────────────┘
```

### Recommended Workflow

1. **Import** — Upload `.csv`, `.xlsx`, `.txt`, or `.md`, or paste requirements text
2. **Elaborate** *(optional)* — AI pre-analyses requirements, extracts entities, enriches context
3. **Plan Modules** — AI detects all SWCs; module cards appear showing ASIL, complexity, runnables
4. **Select a Module** — Click a card or use the dropdown to choose one SWC
5. **Generate MUD Spec** — AI produces a detailed Markdown spec (ports, data types, signal ranges, IRVs, CalPrm)
6. **AI Review Spec** *(optional)* — Reviewer checks coverage, safety rules, naming; shows issues per section
7. **Download .md** — Save the MUD spec as a standalone Markdown file
8. **Use for Diagrams →** — Switch back to diagram mode with the selected module as context
9. **Generate Diagrams** — Select diagram types, pick a pipeline mode, click Generate
10. **Export** — Mermaid, draw.io, PlantUML, XMI, SVG, or C-code skeleton

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
REQ_ID | Type       | Description                  | Priority  | ASIL
REQ-001 | functional | Fuse radar and camera data   | must_have | ASIL-B
REQ-002 | safety     | Trigger braking in <100ms    | must_have | ASIL-D
```

### Markdown table

```markdown
| Req_ID  | Type       | Description                | ASIL   |
|---------|------------|----------------------------|--------|
| REQ-001 | functional | Fuse radar and camera data | ASIL-B |
```

> **Tip:** Sample files are in `data/sample/` — try `eps_requirements.csv` for an ASIL-D full example, or `Motcontrolcomp/` for a multi-file motor control case.

---

## REST API

All endpoints at `http://127.0.0.1:8042/api/v1/`. Interactive docs at `/docs`.

### Core Pipeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Server health + AI backend status |
| `GET` | `/config` | Current (non-sensitive) config |
| `POST` | `/config` | Update AI backend config at runtime |
| `POST` | `/requirements/import` | Upload file (multipart) |
| `POST` | `/requirements/import/text` | Paste raw text |
| `POST` | `/elaborate` | AI pre-analysis of requirements |
| `POST` | `/generate` | AI diagram generation (sync) |
| `POST` | `/generate/stream` | AI diagram generation (SSE streaming) |
| `POST` | `/validate` | Validate existing generation result |

### Enhanced Workflow — Module Planning & MUD Spec *(new)*

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/modules/plan` | Stage 1.75 — AI detects SWC modules from requirements |
| `POST` | `/modules/mud-spec` | Stage 2 — Generate MUD spec Markdown for one SWC (SSE stream) |
| `POST` | `/modules/review` | Stage 2b — AI review of a generated MUD spec |

### Export & Traceability

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/export` | Export to `xmi`, `plantuml`, `mermaid`, `drawio` |
| `POST` | `/export/mermaid/inline` | Mermaid text inline (used by Web UI) |
| `POST` | `/export/c-skeleton` | Generate C-code skeleton from activity diagrams |
| `POST` | `/render` | Render to SVG/PNG via Kroki.io |
| `GET` | `/traceability` | Full traceability matrix + coverage |
| `GET` | `/traceability/requirement/{id}` | Traces for one requirement |
| `POST` | `/traceability/accept` | Mark element as human-reviewed |
| `GET` | `/guidelines/status` | Design guidelines status + doc count |
| `POST` | `/guidelines/clear-cache` | Clear guidelines embedding cache |
| `POST` | `/prompts/reload` | Hot-reload prompt YAML templates |
| `POST` | `/ai/test` | Test active AI backend connectivity |

---

## Prompt Templates

All prompts are in `python-sidecar/prompts/` as YAML files with Jinja2 templating.

| Template | Version | Description |
|----------|---------|-------------|
| `activity_diagram.yaml` | v3.0 | AUTOSAR activity/code-flow diagrams with IRV/ExclusiveArea/CalPrm patterns |
| `class_diagram.yaml` | v1.1 | SWC internal structure with IRVs (private attrs), CalPrm (constant attrs), ExclusiveAreas |
| `component_diagram.yaml` | v1.1 | Port topology with ASIL-D safety annotations, CalPrm R-Ports, CompositionSWC |
| `sequence_diagram.yaml` | v1.1 | RTE call flows + IRV self-messages + ExclusiveArea bracket pattern |
| `state_machine_diagram.yaml` | v1.1 | Mode management FSMs with SAFE_STATE + `Dem_SetEventStatus` (ASIL-C/D) |
| `elaboration.yaml` | v1.2 | Requirement pre-analysis: extracts SWCs, IRVs, ExclusiveAreas, CalPrm, ASIL, timing |
| `activity_diagram_generic.yaml` | v2.0 | Generic C-project activity diagrams (no AUTOSAR) |
| `class_diagram_generic.yaml` | v2.0 | Generic C module/struct/function class diagrams |
| `component_diagram_generic.yaml` | v2.0 | Generic C component diagrams (function_call, shared_memory, callback interfaces) |
| `sequence_diagram_generic.yaml` | v2.0 | Generic C sequence diagrams (ISR, Task, Module, Driver lifelines) |
| `state_machine_diagram_generic.yaml` | v2.0 | Generic C state machine diagrams |

Templates support two generation profiles:
- **`autosar`** — AUTOSAR-specific naming, RTE APIs, port conventions (default)
- **`generic_c`** — Plain C projects without AUTOSAR toolchain

---

## AUTOSAR Conventions

The tool enforces AUTOSAR naming conventions automatically:

| Element | Pattern | Example |
|---------|---------|---------|
| SWC | `SWC_PascalCase` | `SWC_SensorFusion` |
| Runnable | `RE_PascalCase` | `RE_FuseSensorData` |
| Provided Port | `PP_PascalCase` | `PP_FusedData` |
| Required Port | `RP_PascalCase` | `RP_RadarInput` |
| CalPrm Port | `RP_CalPrm_PascalCase` | `RP_CalPrm_AssistGain` |
| SR Interface | `IF_SR_PascalCase` | `IF_SR_FusedSensor` |
| CS Interface | `IF_CS_PascalCase` | `IF_CS_SafetyCheck` |
| Prm Interface | `IF_Prm_PascalCase` | `IF_Prm_AssistGain` |
| ExclusiveArea | `EA_PascalCase` | `EA_TorqueData` |
| IRV attribute | `irv_camelCase` | `irvAssistTorque` |

Violations are flagged as `AUT-006` warnings in the validation report.

### Validation Rules

| Rule ID | Category | Description |
|---------|----------|-------------|
| `STR-001` to `STR-015` | Structural | Lifeline IDs, orphan detection, state count |
| `AUT-001` to `AUT-010` | AUTOSAR | Port direction, runnable triggers, naming, ASIL-C/D SAFE_STATE |
| `CON-001` to `CON-005` | Consistency | Cross-diagram element matching |

---

## Configuration Reference

All settings use the `MUD_` prefix in `python-sidecar/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MUD_HOST` | `127.0.0.1` | Server bind address |
| `MUD_PORT` | `8042` | Server port |
| `MUD_DEBUG` | `false` | Enable hot-reload |
| `MUD_LOG_LEVEL` | `info` | Logging level (`debug`/`info`/`warning`) |
| `MUD_AI_BACKEND` | `cloud` | `cloud`, `local`, or `auto` |
| `MUD_CLOUD_PROVIDER` | `anthropic` | `anthropic` or `openai_compatible` |
| `MUD_ANTHROPIC_API_KEY` | — | **Required for Anthropic cloud AI** |
| `MUD_ANTHROPIC_MODEL` | `claude-sonnet-4-5-20250514` | Claude model |
| `MUD_OPENAI_API_KEY` | — | Key for OpenAI-compatible endpoint |
| `MUD_OPENAI_BASE_URL` | — | e.g. `http://localhost:11434/v1` (Ollama) |
| `MUD_OPENAI_MODEL` | `mistral` | Model name for the endpoint |
| `MUD_LOCAL_MODEL_PATH` | — | Path to `.gguf` model file |
| `MUD_LOCAL_MODEL_AUTO_GPU` | `true` | Auto-detect CUDA/Metal GPU |
| `MUD_LOCAL_MODEL_N_GPU_LAYERS` | — | Override GPU layers (-1=all, 0=CPU) |
| `MUD_CONFIDENCE_THRESHOLD` | `0.6` | Minimum AI confidence to accept output |
| `MUD_MAX_RETRIES` | `3` | AI generation retry count |
| `MUD_PIPELINE_MODE` | `two_model` | `single_pass` / `multi_pass` / `two_model_fast` / `two_model` |
| `MUD_PIPELINE_GENERATOR_MODEL` | — | Model for the generator role (two-model pipeline) |
| `MUD_PIPELINE_REVIEWER_MODEL` | — | Model for the reviewer role (two-model pipeline) |
| `MUD_USE_KROKI` | `true` | Enable SVG/PNG rendering via Kroki.io |
| `MUD_KROKI_BASE_URL` | `https://kroki.io` | Kroki.io server URL |
| `MUD_PLANTUML_JAR_PATH` | — | Path to `plantuml.jar` for offline rendering |
| `MUD_VALIDATION_STRICT_MODE` | `false` | Fail on warnings as well as errors |
| `MUD_GUIDELINES_ENABLED` | `true` | Inject design guidelines into generation context |

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

This creates a virtual environment, installs all dependencies, and copies `.env.example` → `.env`.

### Step 2 — Configure AI backend

Edit `python-sidecar/.env`:

```env
# Option A: Anthropic Claude (cloud, best quality)
MUD_AI_BACKEND=cloud
MUD_CLOUD_PROVIDER=anthropic
MUD_ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
MUD_ANTHROPIC_MODEL=claude-sonnet-4-5-20250514

# Option B: Ollama (local, free — run: ollama serve)
MUD_AI_BACKEND=cloud
MUD_CLOUD_PROVIDER=openai_compatible
MUD_OPENAI_BASE_URL=http://localhost:11434/v1
MUD_OPENAI_API_KEY=ollama
MUD_OPENAI_MODEL=qwen2.5-coder
```

### Step 3 — Start the server

```bat
run.bat
```

Open **http://127.0.0.1:8042/** in any browser.

---

## Project Structure

```
MUD/
├── python-sidecar/                    # Python FastAPI AI backend
│   ├── src/mudtool/
│   │   ├── ai/
│   │   │   ├── orchestrator.py        # Central AI router (prompt render, retry, confidence)
│   │   │   ├── pipeline.py            # 4 pipeline modes (single/multi/two_model)
│   │   │   ├── module_planner.py      # ★ Stage 1.75 — SWC module decomposition from reqs
│   │   │   ├── mud_spec_generator.py  # ★ Stage 2   — MUD Spec Markdown + AI review
│   │   │   ├── elaborator.py          # Stage 1.5  — requirement pre-analysis
│   │   │   ├── chunked_elaborator.py  # Large requirement set chunked elaboration
│   │   │   ├── prompt_engine.py       # Jinja2 YAML prompt renderer
│   │   │   ├── skill_loader.py        # Skill/guideline loader
│   │   │   ├── guidelines_reader.py   # Design guidelines RAG context injection
│   │   │   ├── visual_qa.py           # Mermaid QA linter pass
│   │   │   ├── cloud_backend.py       # Anthropic Claude + OpenAI-compatible backends
│   │   │   ├── local_backend.py       # llama.cpp GGUF local backend
│   │   │   └── base_backend.py        # Abstract backend interface
│   │   │
│   │   ├── api/
│   │   │   ├── routes.py              # All FastAPI endpoints (incl. /modules/* new)
│   │   │   └── dependencies.py        # Dependency injection (orchestrator, validator, etc.)
│   │   │
│   │   ├── config/
│   │   │   └── settings.py            # Pydantic-settings with MUD_ env vars
│   │   │
│   │   ├── generator/
│   │   │   ├── autosar_mapper.py      # AUTOSAR naming post-processing
│   │   │   ├── mermaid_exporter.py    # JSON → Mermaid text
│   │   │   ├── drawio_exporter.py     # JSON → draw.io XML
│   │   │   ├── plantuml_exporter.py   # JSON → PlantUML
│   │   │   ├── xmi_exporter.py        # JSON → UML 2.x XMI
│   │   │   ├── c_skeleton_exporter.py # ActivityDiagram → C-code skeleton
│   │   │   └── render_service.py      # Kroki.io SVG/PNG rendering
│   │   │
│   │   ├── importers/
│   │   │   ├── factory.py             # Auto-detect file format
│   │   │   ├── csv_importer.py
│   │   │   ├── excel_importer.py
│   │   │   ├── text_importer.py
│   │   │   └── markdown_importer.py
│   │   │
│   │   ├── models/
│   │   │   ├── json_uml.py            # Pydantic UML diagram models
│   │   │   ├── requirements.py        # RequirementSet, Requirement models
│   │   │   ├── validation.py          # ValidationReport, Issue models
│   │   │   └── autosar.py             # AUTOSAR-specific models
│   │   │
│   │   ├── validation/
│   │   │   ├── engine.py              # Validation orchestration
│   │   │   ├── structural_validator.py # STR-001..015 rules
│   │   │   ├── autosar_validator.py   # AUT-001..010 rules (incl. ASIL-C/D SAFE_STATE)
│   │   │   ├── consistency_validator.py # CON-001..005 rules
│   │   │   ├── structural_precheck.py
│   │   │   └── mermaid_linter.py      # Mermaid syntax QA
│   │   │
│   │   ├── traceability/
│   │   │   └── store.py               # SQLite req-to-model element trace store
│   │   │
│   │   └── web/
│   │       ├── app.py                 # FastAPI app factory
│   │       └── templates/
│   │           └── index.html         # Built-in browser dashboard (2850+ lines)
│   │
│   ├── prompts/                       # YAML prompt templates (Jinja2)
│   │   ├── activity_diagram.yaml      # v3.0 AUTOSAR (IRV/ExclusiveArea/CalPrm)
│   │   ├── class_diagram.yaml         # v1.1 AUTOSAR
│   │   ├── component_diagram.yaml     # v1.1 AUTOSAR (CalPrm ports, ASIL annotations)
│   │   ├── sequence_diagram.yaml      # v1.1 AUTOSAR (IRV self-messages)
│   │   ├── state_machine_diagram.yaml # v1.1 AUTOSAR (SAFE_STATE, Dem_SetEventStatus)
│   │   ├── elaboration.yaml           # v1.2 (IRV, ExclusiveArea, CalPrm extraction)
│   │   ├── activity_diagram_generic.yaml      # v2.0 Generic C
│   │   ├── class_diagram_generic.yaml         # v2.0 Generic C
│   │   ├── component_diagram_generic.yaml     # v2.0 Generic C
│   │   ├── sequence_diagram_generic.yaml      # v2.0 Generic C
│   │   └── state_machine_diagram_generic.yaml # v2.0 Generic C
│   │
│   ├── tests/                         # Pytest unit + integration tests
│   └── pyproject.toml
│
├── modelio-plugin/                    # Java Modelio plugin (optional)
│   └── src/main/java/com/mudtool/
│
├── common/
│   └── schemas/json_uml_schema.json   # JSON Schema for AI interchange format
│
├── data/
│   ├── sample/
│   │   ├── sample_requirements.csv    # ADAS sensor fusion (15 reqs — quick demo)
│   │   ├── eps_requirements.csv       # EPS ASIL-D (55 reqs — full with CalPrm)
│   │   └── Motcontrolcomp/            # PMSM FOC motor control (multi-file, gold standard)
│   │       ├── 00_Overview.csv        # SpdCtrl / CurrCtrl / MtrMon components
│   │       ├── 01_SigFlow.csv         # Signals with data types and physical ranges
│   │       └── 06_AllRunnables.csv    # Runnables with timing budgets
│   ├── guidelines/                    # Design guideline docs (injected into AI context)
│   │   ├── README.md
│   │   └── MUD_SKILL_APPENDIX.md
│   └── skills/
│       └── MUD_SKILL_CORE.md
│
├── output/                            # Generated files land here
├── setup.bat / setup.sh               # First-time install
├── run.bat   / run.sh                 # Start server
├── run_tests.bat / run_tests.sh       # Run test suite
└── demo.bat                           # Offline demo (no API key)
```

---

## AI Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Client (Browser / curl / Modelio plugin)                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP REST (port 8042)
┌──────────────────────────▼──────────────────────────────────────┐
│  FastAPI Sidecar                                                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Enhanced Workflow Stages                                    │ │
│  │                                                              │ │
│  │  1.5  RequirementElaborator ─── YAML: elaboration.yaml      │ │
│  │       Extracts: SWCs, runnables, ports, IRVs,               │ │
│  │                CalPrm, ASIL, timing, ExclusiveAreas          │ │
│  │                                                              │ │
│  │  1.75 ModulePlanner ──────────── focused system prompt       │ │
│  │       → ModuleInfo[]: swc_name, asil, runnables,            │ │
│  │                        req_ids, complexity                   │ │
│  │                                                              │ │
│  │  2    MudSpecGenerator ──────── structured Markdown template │ │
│  │       → 7-section MUD Spec .md per selected SWC              │ │
│  │         (Ports / Runnables / IRVs / CalPrm / Safety)         │ │
│  │                                                              │ │
│  │  2b   MudSpecGenerator.review_spec() ── AI reviewer prompt   │ │
│  │       → SpecReviewResult: approved, coverage%, issues[]      │ │
│  │                                                              │ │
│  │  3    AIOrchestrator.generate_diagram()                      │ │
│  │       ├── PromptEngine (Jinja2 YAML templates, 11 files)     │ │
│  │       ├── Pipeline (single_pass / multi_pass / two_model)    │ │
│  │       └── Diagram types: Seq│SM│Class│Comp│Activity          │ │
│  │                                                              │ │
│  │  4    3-pass Validation (STR + AUT + CON rules)              │ │
│  │  5    Exporters: Mermaid│drawio│PlantUML│XMI│SVG│C-skeleton  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Traceability Store (SQLite — req → model element links)          │
│  Guidelines RAG (chunk + inject design guidelines into context)   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ backend selection (auto / cloud / local)
          ┌────────────────┴───────────────────┐
          │                                    │
┌─────────▼──────────┐             ┌───────────▼────────────┐
│  Cloud Backend      │             │  Local Backend          │
│                     │             │                         │
│  Anthropic Claude   │             │  Ollama (via OpenAI API)│
│  claude-sonnet-4-5  │             │  qwen2.5-coder:7b       │
│                     │             │  qwen2.5:7b             │
│  OpenAI-compatible  │             │  codellama / mistral    │
│  GPT-4o / Groq /    │             │  llama3.2 / gemma2:2b   │
│  Together.ai / etc. │             │                         │
│                     │             │  llama.cpp GGUF         │
│                     │             │  (auto GPU detection)   │
└─────────────────────┘             └─────────────────────────┘
```

### Two-Model Pipeline (best quality)

```
Requirements
    │
    ▼
Generator Model (qwen2.5-coder / codellama)
    │  Draft diagram JSON
    ▼
Reviewer Model (qwen2.5 / mistral)
    │  Critique: naming, ASIL rules, coverage gaps
    ▼
Refiner (same model as generator)
    │  Refined diagram JSON
    ▼
Validation (structural + AUTOSAR + consistency)
    │
    ▼
Final Output + Traceability Links
```

---

## Export Formats

| Format | Extension | Best for | Tool |
|--------|-----------|----------|------|
| **MUD Spec** | `.md` | Implementation handoff | Any Markdown viewer |
| **Mermaid** | `.mmd` | GitHub/Docs/Obsidian | GitHub, Notion, VS Code |
| **draw.io** | `.drawio` | Editing + sharing | app.diagrams.net (free) |
| **PlantUML** | `.puml` | Git diffs, CI | PlantUML online / IntelliJ |
| **XMI UML 2.x** | `.xmi` | Modelio/Papyrus import | Modelio (free) |
| **SVG/PNG** | `.svg` `.png` | Reports, PowerPoint | Any browser/viewer |
| **C-Code Skeleton** | `.c` | Runnable stub generation | GCC, MSVC, any C compiler |

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'mudtool'`
Run `setup.bat` first to install the package.

### Server starts but Web UI shows "AI: offline"
Check `python-sidecar/.env` — ensure `MUD_ANTHROPIC_API_KEY` or `MUD_OPENAI_BASE_URL` is set.

### Port 8042 already in use
```env
MUD_PORT=9000
```

### Generation returns empty diagrams
- Check `/api/v1/health`
- Lower confidence threshold: `MUD_CONFIDENCE_THRESHOLD=0.4`
- Check terminal logs from `run.bat`

### Plan Modules returns no results
- Ensure requirements are imported first (at least 3–5 requirements)
- Try elaborating first (Stage 1.5) for richer context
- Check AI backend is responding (`/api/v1/ai/test`)

### MUD Spec generates but is very short
- The model may be hitting context limits — try a larger model
- Check `MUD_PIPELINE_GENERATOR_MODEL` for Ollama users

### SVG export fails
SVG/PNG uses [Kroki.io](https://kroki.io) (requires internet). For offline:
```env
MUD_USE_KROKI=false
MUD_PLANTUML_JAR_PATH=C:\tools\plantuml.jar
```

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

```bat
demo.bat
```

Tests the full pipeline (import, validate, export) without AI generation.

---

## Optional: Modelio Plugin

Native Modelio IDE integration. Build with Maven, install the `.jmdac` file, configure `mudtool.sidecar.url=http://127.0.0.1:8042`.

---

## License

Proprietary. All rights reserved.
