# The MUD_MUT pipeline: requirements → flow charts → unit tests

This document walks the full ASPICE-aligned flow end to end and explains the seam between the two halves.

```
 requirements.csv/xlsx
        │  (mud-tool: import → elaborate → module planning → MUD spec → AI review)
        ▼
 Activity / Code-Flow diagram  ──(mud-tool: /api/v1/export  format=c_skeleton)──►  <Module>.c
        │                                                                              │
        │                                                                              ▼
        │                                        bridge/mud_to_tests.py  places it in cpputest-rag/c_projects/<Module>/
        │                                                                              │
        │                                        (cpputest-rag: /analyze-project → /generate-tests → /run-tests)
        ▼                                                                              ▼
 requirement IDs  ───────────────── traceability record (bridge/out/<Module>_trace.json) ─────────────── Test_*.cpp
```

## Stage-by-stage

### 1. Design (mud-tool, port 8042)
1. **Import** requirements (`/api/v1/requirements/import`).
2. **Module planning** (`/api/v1/modules/plan`) — AI proposes the SWC decomposition; you pick one module.
3. **MUD spec** (`/api/v1/modules/mud-spec`) — detailed Markdown spec for the module.
4. **AI review** (`/api/v1/modules/review`) — coverage %, issues, ASIL checks.
5. **Generate** (`/api/v1/generate`) — produces a `GenerationResult` containing the diagrams, including the
   **Activity/Code-Flow** flow chart. Each element carries `source_requirements` / `trace_req` for traceability.

Everything above runs on local 7B models when `MUD_AI_BACKEND` points at Ollama/llama.cpp.

### 2. The seam — C skeleton export
`mud-tool` turns the Activity/Code-Flow diagram into a `.c` skeleton via `CSkeletonExporter`, exposed at:

```
POST /api/v1/export
{ "format": "c_skeleton", "result": <GenerationResult>, "output_path": "<dir>" }
```

The emitted `.c` preserves requirement traceability as header/inline comments
(`/* Requirements: ... */`, per-node trace comments) and RTE call structure — exactly the input the verification
half understands.

### 3. Verification (cpputest-rag, port 8000)
1. **Analyze** (`GET /analyze-project?project_path=<Module>`) — extract function signatures + complexity.
2. **Generate tests** (`POST /generate-tests {"project_path": "<Module>"}`) — FAISS RAG retrieves similar example
   tests, CodeLlama-7B writes `Test_*.cpp` + a coverage-enabled `Makefile`.
3. **Build & run** (`POST /run-tests?test_directory=<dir>`) — the CppUTest Docker runner compiles, runs, and
   produces LCOV/HTML/JUnit coverage.

### 4. Traceability (the bridge)
`bridge/mud_to_tests.py` ties it together and writes `bridge/out/<Module>_trace.json`:

```json
{
  "module": "SWC_MyModule",
  "source_requirements": ["REQ_012", "REQ_045"],
  "design_artifact": "SWC_MyModule.c (MUD Activity/Code-Flow skeleton)",
  "generated_tests": { "test_files": ["Test_Foo.cpp", "Test_Bar.cpp"], "...": "..." },
  "trace": [ { "requirement": "REQ_012", "verified_by": ["Test_Foo.cpp"] } ]
}
```

That JSON is the ASPICE artifact the two tools couldn't produce separately: **requirement → design → test**.

## Running the bridge

```bash
# Mode A — from an already-exported skeleton (no mud-tool server needed):
python bridge/mud_to_tests.py --skeleton path/to/SWC_MyModule.c --module SWC_MyModule --run

# Mode B — from a mud-tool GenerationResult JSON (bridge calls /export for you):
python bridge/mud_to_tests.py --result path/to/generation_result.json --module SWC_MyModule --run
```

Prerequisites: Ollama running with the models from the [README](../README.md#quick-start-100-local); the
cpputest-rag backend up (`docker compose up`); for Mode B, `mudtool-server` running on 8042.

## Roadmap — backend parity & test-side guardrails
- Give `cpputest-rag` the same `LOCAL | CLOUD | AUTO` backend abstraction as `mud-tool`, so the test half also
  offers a cloud/API option (today it is Ollama-only).
- Wrap `test_generator.py` in a **generate → compile/run → reviewer → regenerate** guardrail loop (the
  `/run-tests` compile step already exists — feed failures back to a reviewer model), mirroring `mud-tool`'s
  generator↔reviewer pipeline so 7B test output is self-correcting.
