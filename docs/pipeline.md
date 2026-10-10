# The MUD_MUT pipeline: requirements → flow charts → unit tests

The pipeline diagram lives in the [README](../README.md#pipeline-at-a-glance) — keep it current there.
Everything runs in-process (`mudmut_core`) inside WSL; no Docker, no services required.

## Stage by stage — and where each output lands

| # | Stage | Engine call | Model stage (Workflow & Models) | Output in `outputs/<run>/` |
|---|---|---|---|---|
| 1 | Import requirements (CSV/XLSX/ReqIF/MD/TXT; DOORS, Polarion, Jira column names recognised, HTML text cleaned, odd IDs normalised) | `design.import_requirements` | — | `00_input/requirements.json` |
| 2 | Plan modules (SWC split) | `design.plan_modules` | `planner` | (selected SWC in `state.json`) |
| 3 | MUD spec | `design.generate_mud_spec` (`single_pass` / `two_stage`) | `mud_spec_skeleton`, `mud_spec_generator` | `01_mud/mud_spec.md` |
| 4 | Review (full mode) | `design.review_and_improve` | `mud_spec_reviewer` | `01_mud/review.json` |
| 5 | Activity / code flow | `design.generate_activity` (AI, or deterministic from Section 7 in quick mode / on placeholder) | `activity_*` | `01_mud/activity.json`, `flow.mmd` |
| 6 | C skeleton + compilable | `design.export` → `compilable.make_compilable` (gcc in WSL) | — | `02_code/<SWC>.c/.h`, `Rte_*`, `compilability.json` |
| 7 | Generate tests | `verify.generate_tests` (RAG + LLM per function) | `test_generator`, `rag_embed` | `03_mut/Test_*.cpp`, `Makefile`, `build_and_run.sh`, `build_and_run.bat` |
| 8 | Build, run, fix (Makefile generated per run from the CppUTest folder in **Settings**) | `verify.fix_loop` (make in WSL, fix loop, quarantine, smoke fallback) | `test_fixer` | `03_mut/test-results.xml`, `coverage_html/`, `test-report.html`, `quarantined/` |
| 9 | Traceability | `trace.build_trace` | — | `04_trace/trace.json` |
| 10 | Report | `report.write_run_report` | — | `RUN_REPORT.md`, `run.json` |

`RUN_REPORT.md` gives a ✅ / ⚠️ / ❌ verdict per stage (a failed run marks the failing stage ❌ and
later stages "—"), the provider + model used by every stage, timings, compile ratio, JUnit counts,
coverage, the trace summary, and **"Data sent to cloud: …"**.

## Re-running the tests by hand

Every run's `03_mut/` folder gets a generated `Makefile` plus `build_and_run.sh` (WSL/Linux) and
`build_and_run.bat` (Windows, calls the `.sh` through `wsl.exe`). They are written by every path —
UI, Full Chain, CLI and the OpenCode agent — and use the CppUTest folder from Settings. Run
`build_and_run.bat` (or `./build_and_run.sh`) to compile, run and produce coverage; pass make targets
(`test`, `clean`, …) as arguments.

## Running it

- **UI:** `launch.bat` / `./launch.sh` → http://localhost:8501 → *Full Chain* (or step by step via
  *Design MUD* and *Unit Tests MUT*).
- **CLI:**
  ```bash
  python -m mudmut_core.chain --requirements inputs/requirements/samples/bms_requirements.csv \
      --swc SWC_BatteryManagement --quick
  ```
  Without `--preset` the run uses your current per-stage selection (Workflow & Models) and does not
  change it. `--preset <id>` (from `config/presets.json`) applies that preset first.
- **Agent:** the *OpenCode Agent* page drives `mud-designer`, which calls `agentic/tools/mudmut_cli.py`
  (same engine, same `outputs/<run>/` layout). See [agentic/README.md](../agentic/README.md).

## Models and providers

Each stage has a provider (Ollama local, OpenRouter, NVIDIA, DeepSeek, Google) and a model; see
[providers.md](providers.md). Embedding stages and visual QA are Ollama-only. Cloud providers receive
requirement text and designs — the run report always says which ones did.

## Traceability rule

A requirement is `verified_by_test` only when the test file of a function whose design carries its ID
ran and every case passed; `failing_test` if it ran with failures; `test_not_run` if the test exists
but produced no results; `not_verified` otherwise.
