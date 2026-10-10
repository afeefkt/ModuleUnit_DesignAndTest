# cpputest-rag — the verification half (MUT) as a library

Generates CppUTest unit tests for C code with local or cloud LLMs, using RAG over example tests,
then builds and runs them with coverage. In MUD_MUT it is used **in-process** by `mudmut_core`
(no Docker, no separate service). Start everything from the repo root — see the main
[README](../README.md).

## What it does
1. **Analyze** C sources (`app/services/c_parser.py`): functions, signatures, complexity.
2. **Retrieve** similar example tests (`app/services/rag_engine.py`): FAISS over
   `inputs/test_examples/`, Ollama embeddings (`EMBED_MODEL`, default `all-minilm`).
3. **Generate** one `Test_<function>.cpp` per function (`app/services/test_generator.py`) through
   the multi-provider client (`mudmut_core.llm`) with the **Test generator** stage's provider + model.
4. **Build & run** (`mudmut_core.verify`): the generated `Makefile` (CppUTest from apt,
   `CPPUTEST_HOME ?= /usr`) builds in WSL/Linux, runs the tests (JUnit XML) and produces lcov/HTML
   coverage. A fix loop repairs tests that don't compile; files that still fail are moved to
   `quarantined/` and reported.

Outputs land in the run folder `outputs/<run>/03_mut/` (tests, Makefile, `test-results.xml`,
`coverage.info`, `coverage_html/`, `test-report.html`).

## Settings
Paths and models are set by `mudmut_core/env.py` and the stage registry (Workflow & Models page):
`TEST_EXAMPLES_DIR`, per-run `OUTPUT_DIR`, `GEN_MODEL` / `TEST_GEN_PROVIDER`,
`FIX_MODEL` / `TEST_FIX_PROVIDER`, `EMBED_MODEL`, `REQUEST_TIMEOUT` (default 1800 s).

## Toolchain (once, in WSL)
```bash
sudo apt-get install -y build-essential cpputest lcov
```

## Optional FastAPI service
`backend/app/main.py` still exposes the original REST API (`uvicorn app.main:app` from
`cpputest-rag/backend`) and builds tests natively via `app/services/native_runner.py`. The
Streamlit platform does not need it.
