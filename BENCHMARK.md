# BENCHMARK — what MUD_MUT has produced so far

Every number below comes from a run folder in `outputs/` and is printed next to that folder's name.
The tables between the markers are generated, not typed:

```bash
python -m mudmut_core.benchmark --write BENCHMARK.md   # in the project venv (WSL)
```

All output of MUD_MUT is an AI-assisted draft for engineer review, not qualified or certified tooling.
These runs are the development history of the tool, not a controlled experiment: models, prompts and
code changed between them, and each configuration ran once (variance is not measured yet).

## Summary (as of 2026-11-10)

- **No requirement is yet verified by a test whose expected value comes from the requirement or the
  design.** This is the open problem the next work targets (a design-derived test oracle).
- **Local models (qwen3 8B for design, qwen2.5 7B for tests), 5 finished runs** (BMS sample ×3, hardened AEB
  ×1, one agent run on the EPS sample): in 4 of them no AI-written test file compiled, so only the built-in
  smoke test ran (it checks nothing). In one BMS run 1 of 5 test files compiled (4 cases passed, 1 failed).
  `verified_by_test`: 0 in all five (0 of 30 on the BMS sample).
- **Cloud model (DeepSeek, hardened AEB set), 6 runs, 3 finished:** in 2 of the 3 finished runs the AI-written
  tests compile (2 of 4 and 2 of 2 files); in the third none did. One run (`20261109_004201_…`) marks
  **18 of 21** requirements `verified_by_test`, but 11 of those 18 rest only on a test file whose every case
  is `CHECK_TRUE(true)` against a stub, and the other 7 on expected values the model read from the generated
  C code. The latest run marks 0 of 118 (all `failing_test`; 10 of 15 cases passed). The other 3 cloud runs
  stopped early (no activity diagram, an HTTP 400 from the provider, one cancel).
- **C skeleton:** 0–51 % of the design statements were commented out to make the C compile; three cloud
  runs also lost design logic or left values unassigned, which the run report marks ❌.
- **Run time:** about 12.5–14.3 min per quick local run; 1.6–8 min per cloud run.

## Environment

Recorded 2026-11-10 on the machine the runs were made on. The runs themselves did not record hardware,
tool versions or model digests, so these are today's values (P1.3 adds them to every run).

| Item | Value |
|---|---|
| CPU / RAM | Intel Core Ultra 7 155H · 15.5 GB (WSL sees 4 CPUs, 3 GB) |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU, 8 GB (driver 610.60) |
| OS | Windows 11 Home 10.0.26300 · WSL 2, Ubuntu 26.04 LTS (kernel 6.18.33.2) |
| Build | gcc / g++ 15.2.0 · GNU Make 4.4.1 · lcov 2.0-1 · CppUTest 4.0 (built in `Tools/cpputest-install`) |
| Python | 3.14.4 (project venv) |
| Ollama | 0.40.15 |

Local models used by the runs (Ollama ID today; Ollama shows each as last modified 3–8 months ago, before the
first run on 2026-10-10, so these are the models the runs used):

| Model | Ollama ID | Used for |
|---|---|---|
| `qwen3:8b-ctx16384` | `7ef4ca800d20` | planner, MUD spec, activity (local runs) |
| `qwen2.5:7b` | `845dbda0ea48` | test generator and test fixer (local runs) |
| `nomic-embed-text:latest` | `0a109f422b47` | guidelines RAG (local runs) |
| `bge-m3:latest` | `790764642607` | guidelines RAG (cloud runs) |
| `all-minilm:latest` | `1b226e2802db` | test-example RAG |
| `llava:7b` | `8dd30f6b0cb1` | visual QA stage (configured) |

Cloud runs used `deepseek-chat` and `deepseek-reasoner` through the DeepSeek API on 2026-11-08/09; the
provider does not expose a model digest. Temperature and seed were not recorded per run.

## How to read the columns

- **Input** — the file under `inputs/` whose requirement IDs equal the run's `00_input/requirements.json`.
- **Statements kept / total, Stubbed %** — from `02_code/compilability.json`: design statements that stayed
  C vs. those commented out (`TODO(design)`) so the skeleton compiles.
- **AI test files generated / compiled / quarantined** — compiled = generated − quarantined; 0 when only the
  smoke test ran. Quarantined files did not compile after the fix loop.
- **Results from** — `AI` (AI-written tests ran) or `smoke` (none compiled; the built-in smoke test calls each
  runnable once and checks nothing).
- **`verified_by_test`** — the trace rule in `mudmut_core/trace.py`: the test file of a function whose design
  carries the requirement ID ran and every case in it passed.
- **Backed by a real assertion** — of those, the requirements with at least one passing test file that
  compares a computed value (e.g. `LONGS_EQUAL`). A requirement backed only by **no-op test files**
  (every case asserts a constant, e.g. `CHECK_TRUE(true)`) is not counted.
- Even a real assertion here checks what the **code** does: the test generator writes expected values from
  the C skeleton, not from the requirement or the MUD spec.

## Results

<!-- BEGIN GENERATED: python -m mudmut_core.benchmark --write BENCHMARK.md -->

_11 run(s) with a report in `outputs/`, oldest first. Stage letters: import · plan · spec · review · activity · compilable · tests · build & run · trace (✅ pass, ⚠️ partial, ❌ failed, — not run). In the number columns — means not recorded (older runs) or not reached (failed runs)._

### Runs

| Run folder | Input (under `inputs/`) | Reqs | Mode | Spec / test model | Data to cloud | Outcome | Stages |
|---|---|---|---|---|---|---|---|
| `20261010_034440_SWC_BatteryManagement_local-recommended` | `requirements/samples/bms_requirements.csv` | 30 | quick | `ollama/qwen3:8b-ctx16384` / `ollama/qwen2.5:7b` | no | finished | ✅✅✅—✅⚠️❌❌✅ |
| `eps` | `requirements/samples/eps_requirements.csv` | 55 | — | `ollama/qwen3:8b-ctx16384` / `ollama/qwen2.5:7b` | no | finished | ✅✅✅—✅✅❌❌✅ |
| `20261010_122539_SWC_BatteryManagement_custom` | `requirements/samples/bms_requirements.csv` | 30 | quick | `ollama/qwen3:8b-ctx16384` / `ollama/qwen2.5:7b` | no | finished | ✅✅✅—✅⚠️✅⚠️✅ |
| `20261010_174728_SWC_BatteryManagement_custom` | `requirements/samples/bms_requirements.csv` | 30 | quick | `ollama/qwen3:8b-ctx16384` / `ollama/qwen2.5:7b` | no | finished | ✅✅✅—✅⚠️❌❌✅ |
| `20261108_221854_SWC_AEB_BrakeActuator_custom` | `requirements_hardened/aeb/aeb_requirements_hardened.csv` | 120 | quick | `ollama/qwen3:8b-ctx16384` / `ollama/qwen2.5:7b` | no | finished | ✅✅✅—✅⚠️❌❌✅ |
| `20261108_231243_SWC_AE_custom` | `requirements_hardened/aeb/aeb_requirements_hardened.csv` | 120 | quick | `deepseek/deepseek-chat` / `deepseek/deepseek-chat` | deepseek | failed at activity: ChainError: activity generation produced no diagrams | ✅✅✅—❌———— |
| `20261108_235924_SWC_AE_custom` | `requirements_hardened/aeb/aeb_requirements_hardened.csv` | 120 | full | `deepseek/deepseek-chat` / `deepseek/deepseek-chat` | deepseek | failed at review: HTTPStatusError: Client error '400 Bad Request' | ✅✅✅❌————— |
| `20261109_000735_SWC_AEB_BrakeActuator_custom` | `requirements_hardened/aeb/aeb_requirements_hardened.csv` | 120 | quick | `deepseek/deepseek-chat` / `deepseek/deepseek-chat` | deepseek | finished | ✅✅✅—✅❌❌❌✅ |
| `20261109_003209_SWC_AEB_BrakeActuator_custom` | `requirements_hardened/aeb/aeb_requirements_hardened.csv` | 120 | full | `deepseek/deepseek-chat` / `deepseek/deepseek-chat` | deepseek | failed at activity: ChainCancelled: Cancelled while an AI request was running | ✅✅✅✅❌———— |
| `20261109_004201_SWC_AEB_BrakeActuator_custom` | `requirements_hardened/aeb/aeb_requirements_hardened.csv` | 120 | quick | `deepseek/deepseek-chat` / `deepseek/deepseek-chat` | deepseek | finished | ✅✅✅—✅❌⚠️⚠️✅ |
| `20261109_005903_SWC_AEB_BrakeActuator_custom` | `requirements_hardened/aeb/aeb_requirements_hardened.csv` | 120 | full | `deepseek/deepseek-chat` / `deepseek/deepseek-chat` | deepseek | finished | ✅✅✅⚠️✅❌✅⚠️✅ |

### Design and C code

| Run folder | Statements kept / total | Stubbed % | Design logic commented out | Read but never assigned | Minutes |
|---|---|---|---|---|---|
| `20261010_034440_SWC_BatteryManagement_local-recommended` | 88 / 119 | 26 | — | — | 12.7 |
| `eps` | 20 / 20 | 0 | — | — | — |
| `20261010_122539_SWC_BatteryManagement_custom` | 77 / 101 | 24 | — | — | 12.8 |
| `20261010_174728_SWC_BatteryManagement_custom` | 37 / 71 | 48 | — | — | 12.5 |
| `20261108_221854_SWC_AEB_BrakeActuator_custom` | 17 / 22 | 23 | — | — | 14.3 |
| `20261108_231243_SWC_AE_custom` | — | — | — | — | — |
| `20261108_235924_SWC_AE_custom` | — | — | — | — | — |
| `20261109_000735_SWC_AEB_BrakeActuator_custom` | 58 / 84 | 31 | 8 | 3 | 2.0 |
| `20261109_003209_SWC_AEB_BrakeActuator_custom` | — | — | — | — | — |
| `20261109_004201_SWC_AEB_BrakeActuator_custom` | 108 / 112 | 4 | 1 | 0 | 1.6 |
| `20261109_005903_SWC_AEB_BrakeActuator_custom` | 94 / 191 | 51 | 0 | 1 | 8.0 |

### Tests and traceability

| Run folder | AI test files generated / compiled / quarantined | Tests passed / failed | Results from | Reqs in trace | `verified_by_test` | of which backed by a real assertion | failing | not verified | No-op test files |
|---|---|---|---|---|---|---|---|---|---|
| `20261010_034440_SWC_BatteryManagement_local-recommended` | 6 / 0 / 6 | 6 / 0 | smoke | 30 | 0 | 0 | 0 | 30 | `Test_Smoke.cpp` |
| `eps` | — / — / — | 1 / 0 | smoke | 12 | 0 | 0 | 0 | 12 | `Test_Smoke.cpp` |
| `20261010_122539_SWC_BatteryManagement_custom` | 5 / 1 / 4 | 4 / 1 ¹ | AI | 30 | 0 | 0 | 30 | 0 | — |
| `20261010_174728_SWC_BatteryManagement_custom` | 4 / 0 / 4 | 3 / 0 | smoke | 30 | 0 | 0 | 0 | 30 | `Test_Smoke.cpp` |
| `20261108_221854_SWC_AEB_BrakeActuator_custom` | 1 / 0 / 1 | 1 / 0 | smoke | 120 | 0 | 0 | 0 | 120 | `Test_Smoke.cpp` |
| `20261108_231243_SWC_AE_custom` | — / — / — | — / — | — | — | — | — | — | — | — |
| `20261108_235924_SWC_AE_custom` | — / — / — | — / — | — | — | — | — | — | — | — |
| `20261109_000735_SWC_AEB_BrakeActuator_custom` | 4 / 0 / 4 | 3 / 0 | smoke | 0 | 0 | 0 | 0 | 0 | `Test_Smoke.cpp` |
| `20261109_003209_SWC_AEB_BrakeActuator_custom` | — / — / — | — / — | — | — | — | — | — | — | — |
| `20261109_004201_SWC_AEB_BrakeActuator_custom` | 4 / 2 / 2 | 11 / 0 | AI | 21 | 18 | 7 | 0 | 3 | `Test_MapDecelToPressure.cpp` |
| `20261109_005903_SWC_AEB_BrakeActuator_custom` | 2 / 2 / 0 | 10 / 5 | AI | 118 | 0 | 0 | 118 | 0 | — |

¹ `03_mut/results.json` holds a later manual rebuild with other numbers; the table shows the results recorded when the run finished (`run.json`).

Not counted:

- `MyRunnableID` — no run report (`run.json` without verdicts)
- `req_hardening/` — not a pipeline run folder

<!-- END GENERATED -->

## Not measured yet

- **Variance** — every configuration ran once. P1.4: the same input three times with a pinned preset.
- **Pinned, reproducible configuration** — no `benchmark-local` preset, digests or temperature per run yet (P1.3).
- **Oracle quality** — expected values from the design instead of the code (P2.2), mutation survivors (P2.3),
  seeded design faults (P2.4).
- **Review effort** — how long an engineer needs to check one module's output.
- **Execution on target** — all tests run on the host (gcc in WSL); no target, HIL or MC/DC.
