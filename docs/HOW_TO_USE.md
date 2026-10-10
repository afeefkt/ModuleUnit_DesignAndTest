# How to use MUD_MUT — step by step

This guide walks through every stage, from installing to reading the final report. Everything the
tool produces is an **AI-assisted draft for engineer review**, not certified output.

**Contents**

1. [Before you start (one-time setup)](#1-before-you-start-one-time-setup)
2. [The screen: run bar, stage rail, menu](#2-the-screen)
3. [First-time check (5 minutes)](#3-first-time-check)
4. [Route A — the Full chain (one click)](#4-route-a--the-full-chain-one-click)
5. [Route B — step by step](#5-route-b--step-by-step)
6. [Read the result: Runs & reports](#6-read-the-result-runs--reports)
7. [Choosing models: local, free cloud, presets](#7-choosing-models)
8. [AI monitor: see what the model receives and answers](#8-ai-monitor)
9. [OpenCode agent (optional automation layer)](#9-opencode-agent)
10. [Re-running the tests by hand](#10-re-running-the-tests-by-hand)
11. [Command line](#11-command-line)
12. [Requirement file formats](#12-requirement-file-formats)
13. [What is in a run folder](#13-what-is-in-a-run-folder)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Before you start (one-time setup)

You need Windows with **WSL (Ubuntu)** — or plain Linux — and **Ollama** for local models.

| Step | Command / action |
|---|---|
| Local models | `ollama pull qwen3:8b`, `ollama pull qwen2.5:7b`, `ollama pull all-minilm`, `ollama pull nomic-embed-text`. Then create the capped model the presets use (see below) |
| Settings preset | `cp .env.local.example .env` |
| Install the app | `setup.bat` (Windows) or `./setup.sh` (WSL/Linux) — creates `.venv` |
| Build tools (WSL, once) | `wsl -u root -e apt-get install -y build-essential cpputest lcov` |
| Start | `launch.bat` (Windows) or `./launch.sh` — then open **http://localhost:8501** |

The presets use `qwen3:8b-ctx16384`, a copy of `qwen3:8b` with a 16k context so it fits an 8 GB GPU. It shares the
weights (no extra download):

```bash
printf 'FROM qwen3:8b\nPARAMETER num_ctx 16384\n' > /tmp/Modelfile
ollama create qwen3:8b-ctx16384 -f /tmp/Modelfile
```

More background: [providers.md](providers.md#local-models-cap-the-context-window-8-gb-gpus).

Notes:

- The first page load after a start takes **10–25 seconds** (the engine is loading). Later pages are quick.
- If you built CppUTest yourself, put it in `Tools/cpputest-install` (found automatically) or set its folder on
  the **Settings** page.
- Cloud keys (optional) are **Windows user variables**: `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`,
  `DEEPSEEK_API_KEY`, `GOOGLE_GENERATIVE_AI_API_KEY`, `OLLAMA_API_KEY` (Ollama Cloud).
  `launch.bat` passes them into WSL. Keys are never written to a file or shown on screen.

---

## 2. The screen

```
┌ menu ─────────┐  Current run  [ 20261010_… ▾ ]       local only
│ Start         │  [Import][Plan][Spec][Review][Activity][Compilable][Tests][Build & run][Trace]
│  Overview     │  ───────────────────────────────────────────────────────────
│ Design        │  Page title
│  Requirements │  …page content…
│  & design     │
│ Verify        │
│  Unit tests   │
│  Full chain   │
│ Review        │
│  Runs &       │
│  reports      │
│  AI monitor   │
│ Setup         │
│  Models       │
│  Keys &       │
│  providers    │
│  Settings     │
│ Agent         │
│  OpenCode     │
└───────────────┘
```

- **Current run** (top of every page): the run you are looking at. Pick another run here and every page follows.
  The badge says **local only** or lists the cloud providers that were used.
- **Stage rail** (the coloured strip): one box per pipeline stage for the current run.
  Green **pass**, amber **partial**, red **failed**, grey **not run**. This is the fastest way to see where a run
  broke or was only partly good.
- **Running job chip**: while a Full chain runs you see "Full chain running — 42 %" on every page. The run
  keeps going when you switch pages.

---

## 3. First-time check

Do this once, in this order:

1. **Start ▸ Overview** — three panels should be green:
   - *Local AI (Ollama)*: "Running — N models". If red, start Ollama and reload (cloud models still work).
   - *Build tools (WSL)*: gcc, g++, make, gcov, **CppUTest**, lcov all ✅. If CppUTest is ❌, go to step 2.
   - *Cloud AI keys*: which cloud providers have a key.
2. **Setup ▸ Settings** — only if CppUTest is missing or you want your own build:
   type the CppUTest folder (it contains `include/CppUTest` and `lib`), press **Check** — it shows the include and
   lib folders it found — then **Save**. Leave it empty to auto-detect.
3. **Setup ▸ Keys & providers** — press **Test connection** on each provider you plan to use.
   Cloud providers also have **Probe free models** (see [section 7](#7-choosing-models)).
4. **Review ▸ AI monitor** — in *Test chat* pick *Ollama (local)* and press **Quick test**. A reply "OK" means the
   local model works. This is the quickest way to confirm a model before a long run.

---

## 4. Route A — the Full chain (one click)

**Verify ▸ Full chain** runs everything: import → plan → spec → activity flow → C skeleton → compilable →
generate tests → build and run → traceability → report.

1. **Requirements file** — a path. The default is the sample `inputs/requirements/samples/bms_requirements.csv`.
   (Use a WSL path such as `/mnt/d/…`.)
2. **Quick mode** (default on) — single-pass spec, no review round, flow built straight from the spec. About
   **13 minutes** on a local 7–8 B model. Switch it off for the two-stage spec plus a review round (slower, more
   thorough).
3. **Models** — *Current selection* uses what you set on the **Models** page and leaves it unchanged. Choosing a
   preset replaces every stage's model first and saves it as your selection.
4. Open **Which model runs each stage** to see exactly which provider and model each stage will use.
5. If any stage uses a **cloud** provider, a warning lists the providers and you must tick
   **I understand — send data to these providers**. Local-only runs need no confirmation.
6. Press **Start full chain**. You see:
   - a **progress bar with a percentage**, the stage ("spec 3/8"), elapsed time and an estimated time left
     (an estimate: it gets better after a few runs; the long spec stage holds the bar at about 70 % until it finishes);
   - the **AI activity** list on the right — every request to the model, live;
   - a **Step log** (expand it) with the messages from each stage.
7. When it finishes, the new run becomes the current run. Open **Review ▸ Runs & reports** to read the results
   ([section 6](#6-read-the-result-runs--reports)).

If a run stops with an error, the message says which stage failed; the partial report is still written.

---

## 5. Route B — step by step

Use this when you want to inspect or change something between stages.

### 5.1 Design ▸ Requirements & design

Work down the page. Each step appears after the previous one is done.

**① Requirements**

1. Keep **Use sample (BMS)** ticked to try the sample, or untick it and **upload** your file (CSV, XLSX, ReqIF,
   Markdown, text — DOORS, Polarion and Jira exports are recognised, see [section 12](#12-requirement-file-formats)).
2. For CSV/XLSX uploads a **Column mapping** box appears. Leave every field on *(auto)* unless the import misses
   columns; then choose which column is the ID, title and description.
3. Press **Import requirements**. You see "Imported N requirement(s)" and a table. **Import notes** lists warnings
   (skipped rows, generated IDs, an unusual file encoding).

**② Plan modules** — press **Plan SWC modules**. The AI groups the requirements into software components (SWCs) and
runnables. A progress bar shows percent and elapsed time. Choose the component in **Select SWC**.

**③ MUD spec** — tick **Quick (single-pass)** for speed, or leave it off for the two-stage spec. Press
**Generate MUD spec**. The spec appears in a text box (editable).

**④ Review** — press **Review** to get a coverage percentage and the number of errors/warnings.
**Improve (regenerate)** asks the AI to fix the issues. **Approve & continue** marks the review as accepted.
You can skip review and go on.

**⑤ Activity flow** — press **Generate flow chart**. The Mermaid flow chart is drawn with **zoom and pan**:
mouse wheel zooms, drag pans, double-click fits, buttons for +, −, Fit, 100 %, fullscreen and **SVG** download.
*Mermaid source* shows the text.

**⑥ C skeleton** — press **Make compilable**. This creates a **new run folder** under `outputs/` and makes the
generated C compile: missing symbols become `TODO(design)` placeholders and only statements that still fail are
commented out. The result line shows how many statements were kept as real C. Press **Send to MUT →** to continue.

> Each press of **Make compilable** creates a new run folder. Step ①–⑤ results live only on the page until then.

### 5.2 Verify ▸ Unit tests

The page works on the **current run** (top bar). It needs the run's C skeleton (`02_code`).

1. **Generate tests** — creates one CppUTest file per function (using example tests as guidance). A progress bar
   shows "function 3 of 6". The tests, a `Makefile` and the helper scripts go into `03_mut/`.
2. **Rebuild & run (+ fix loop)** — builds with `make` in WSL and runs the tests:
   - tests that do not compile get fixed automatically (first deterministic fixes, then up to two AI fix rounds);
   - tests that still fail to compile are **quarantined** (moved to `03_mut/quarantined/`, listed on the page);
   - if no AI test compiles, a built-in **smoke test** calls every runnable once and is clearly labelled.
   The Makefile is regenerated each time from the CppUTest folder in Settings, so after changing Settings you can
   rebuild without regenerating tests.
3. Read the numbers: *Status*, *Passed*, *Failed*, *Fix attempts*, plus **Build output** and **Test output**
   (expand them for the raw text).
4. **Results** — see [section 6](#6-read-the-result-runs--reports): test report, coverage report, test cases.
5. **Write traceability** — builds the requirement ↔ test table. Meaning of the status column:

   | Status | Meaning |
   |---|---|
   | `verified_by_test` | a test for a function whose design carries this requirement ID ran and every case passed |
   | `failing_test` | the test ran and at least one case failed |
   | `test_not_run` | a test exists but produced no results |
   | `not_verified` | no test covers it |

---

## 6. Read the result: Runs & reports

**Review ▸ Runs & reports** is where you judge a run.

1. **Runs** lists every run with its stage verdicts (✅ pass · ⚠️ partial · ❌ failed · — not run) and whether it
   stayed local.
2. Choose **Single run** (the current run) or **Compare two runs** (preset, cloud use, compile result, tests, timings
   side by side).
3. **Test results and coverage** (single run):
   - cards: tests passed / failed, **line coverage %**, **branch coverage %**;
   - a warning lists **quarantined** test files; an info note appears if the results come from the **smoke test**
     instead of AI-written tests;
   - tabs: **Test report** (the HTML report), **Coverage** (the lcov report with a page per source file — both open
     inside the page, or in a new tab with the *Open … in a new tab* button), **Run report** (the Markdown report),
     **Test cases** (a table per test: pass/fail/time/message);
   - the run folder as a Windows path, and **Download this run as ZIP**.
4. **Run report** — the verdict table per stage, the provider and model used for every stage, timings, and the line
   **"Data sent to cloud: …"**.
5. Expanders show the **MUD spec**, the **Flow chart** (zoomable), the **C skeleton** and the **Trace**.

**How to judge a run**

- ✅ everywhere: all stages completed as designed.
- ⚠️ **Compilable**: some statements could not be turned into valid C and were commented out — compare the count
  kept vs stubbed.
- ⚠️ **Build & run**: tests were quarantined, only the smoke test ran, or some tests failed. Test failures are real
  results — compare them with the design before trusting either side.
- ❌: the stage failed; the report says why and later stages show "not run".

---

## 7. Choosing models

**Setup ▸ Models** has two parts.

**Workflows** — five tabs with flow charts of how each workflow uses the models (zoom and pan work here too).

**Agents — provider + model per stage**

- **Presets** (one click, applies to all stages): *Local - recommended*, *Local - fast*, *OpenRouter - free*,
  *NVIDIA NIM*, *DeepSeek*, *Ollama Cloud*. **Reset to defaults** returns to the local preset.
  A preset with no model for a cloud stage takes the first model that passed a probe (below); otherwise it tells you
  the stage kept its old model.
- **Per stage**: choose a **Provider** and a **Model**, then **Apply**. Stages that share one setting say
  "same setting as …". Embedding and visual-QA stages are local only.
- **🆓 Free models only** hides paid models in the cloud lists; **Filter models** narrows the lists.
- Marks next to a model: 🆓 free · ✅ answered a probe · ⚠️ rate-limited or empty reply · ❌ not hosted · 💲 needs credits.

**Keys & providers ▸ Probe free models** (per cloud provider): sends only the fixed prompt "Say OK" — no project data —
to each free model, a few at a time, and remembers the result for 24 hours. Use it before choosing a cloud model,
because free lists are long and partly stale (some models are rate-limited, retired, or need credits).

What "free" means: OpenRouter — price 0; NVIDIA — trial credits (rate-limited); Ollama Cloud — models in the free
plan (shown only after a probe, because others answer "needs credits").

**Privacy:** local Ollama keeps everything on your machine. Cloud providers receive your requirements and designs.
Every run report states which providers were used.

Tip: reasoning models spend tokens "thinking" and may return an empty answer if the limit is small. Prefer a
non-reasoning model for generation stages, or raise the answer-token limit in the AI monitor chat when testing.

---

## 8. AI monitor

**Review ▸ AI monitor** shows what the app and the models say to each other.

- **Is the AI reachable?** — green/red per provider (local Ollama running and how many models; cloud key found).
- **Test chat** — choose provider and model, optionally a system prompt, and type a message (or press **Quick test**).
  The answer streams in live, the model's **Thinking** is shown separately when the model returns it, and you get
  total time, time to first token and an approximate speed. For a cloud provider, tick the confirmation first —
  only what you type is sent. **Clear chat** starts over.
- **Live requests and answers** — a list of every model call from a run or the chat: time, stage, provider/model
  (local or cloud), duration, tokens and speed. Open a call to see **Thinking**, the **Answer**, and **Request sent**
  (system and user prompt). Filter by stage or provider, show **Only problems** (errors and empty answers), **Clear
  list**, or **Download log**. Each run also keeps its calls in `outputs/<run>/llm_log.jsonl`.

Models that do not return thinking show "No thinking text returned" — nothing is invented.

---

## 9. OpenCode agent

An optional layer: an AI agent (`mud-designer`) runs the same pipeline for you through one locked-down command-line
tool. See [agentic/README.md](../agentic/README.md) for details.

1. One-time, in WSL: `curl -fsSL https://opencode.ai/install | bash`.
2. **Agent ▸ OpenCode agent → ① Serve**: press **Start serve** (**Stop serve** to stop).
3. **② Agent & model**: keep `mud-designer`; pick a provider/model or leave the agent's default
   (`ollama/qwen3:8b-ctx16384`).
4. **③ Chat**: for example *"Design and test RE_EstimateSOC from inputs/requirements/samples/bms_requirements.csv.
   Use run id 'demo'."* Watch the live timeline; answer permission requests with **Allow once** or **Reject**;
   **Abort** stops it; **New session** starts clean.
5. **④ Artifacts** shows the latest run's flow chart and report. The run also appears in **Runs & reports**.

The agent may only run `mudmut_cli.py` and write one file (`01_mud/activity.json`). Requirement text is treated as
data, never as instructions.

---

## 10. Re-running the tests by hand

Every run's `outputs/<run>/03_mut/` folder contains a generated `Makefile` and two scripts that use the CppUTest
folder from Settings:

```powershell
cd D:\AI_Learnigns\ModuleUnit_DesignAndTest\outputs\<run>\03_mut
.\build_and_run.bat                # compile, run, coverage  (Windows)
```
```bash
cd /mnt/d/AI_Learnigns/ModuleUnit_DesignAndTest/outputs/<run>/03_mut
./build_and_run.sh                 # the same, in WSL
./build_and_run.sh test            # any make target: all, test, coverage, clean
```

After a run you find `test-results.xml` (JUnit), `coverage.info`, `coverage_html/index.html` and `test-report.html`
in that folder. To run only the test program: `./run_tests -v`.

---

## 11. Command line

```bash
# Whole chain, headless
python -m mudmut_core.chain --requirements inputs/requirements/samples/bms_requirements.csv \
    --swc SWC_BatteryManagement --quick
```

- Without `--preset` the run uses your current per-stage choices and does not change them. `--preset <id>` (see
  `config/presets.json`) applies a preset first.
- The agent's step-by-step tools: `python agentic/tools/mudmut_cli.py <command> --run <id> …` with the commands
  `import-reqs`, `show-req`, `validate-activity`, `export-c`, `render-mermaid`, `make-compilable`, `gen-tests`,
  `build-run`, `trace`, `report` (`--help` on each shows the options).

---

## 12. Requirement file formats

| Format | Notes |
|---|---|
| CSV / Excel (`.xlsx`) | Needs at least an ID, title or description column. Delimiters `, ; tab |` are detected. |
| **DOORS** exports | Columns such as *Absolute Number / Object Identifier*, *Object Heading*, *Object Text* are recognised. |
| **Polarion** exports | *Work Item ID*, *Title*, *Description*, *Status* …; HTML in descriptions is converted to plain text. |
| **ReqIF** (`.reqif`, `.reqifz`) | The standard exchange format of DOORS, Polarion and others. |
| Markdown / text | One requirement per block (see the samples in `inputs/requirements/samples/`). |

Also handled: UTF-8 with BOM, Windows-1252 and UTF-16 files; IDs that are plain numbers or free text are normalised
to `REQ-1234` style (the original is kept in the notes); a missing ID column gets generated IDs `REQ-001…` with a
warning. If your columns have unusual names, use the **Column mapping** box on the Requirements & design page.
Old binary `.xls` and JSON files are not supported.

---

## 13. What is in a run folder

```
outputs/<YYYYMMDD_HHMMSS>_<SWC>_<preset>/
  RUN_REPORT.md            verdict per stage, models used, cloud notice, timings
  run.json                 the same, machine-readable (drives the stage rail)
  llm_log.jsonl            every model call of this run
  00_input/                the imported requirements
  01_mud/                  MUD spec, review, activity JSON, flow chart (.mmd)
  02_code/                 the compilable C skeleton, Rte stubs, compilability report
  03_mut/                  tests, Makefile, build_and_run.sh/.bat, test-results.xml, coverage.info,
                           coverage_html/, test-report.html, quarantined/
  04_trace/                trace.json, trace.md
outputs/LATEST             name of the newest run
```

Runs are never overwritten — every run gets its own folder. To start from scratch, simply start a new run
(or delete the old run folders you no longer need).

---

## 14. Troubleshooting

| What you see | What to do |
|---|---|
| `launch.bat` prints `$'\r': command not found` | The shell scripts have Windows line endings. Run `git add --renormalize .` (the repo forces LF for `*.sh`), or convert `launch.sh` / `setup.sh` to LF. |
| Overview: **Ollama not reachable** | Start Ollama (it listens on `localhost:11434`), then reload. Cloud models need no Ollama. |
| Overview: **CppUTest ❌** | Set the folder on **Settings**, or `wsl -u root -e apt-get install -y cpputest lcov`. |
| Unit tests: "CppUTest was not found" | Same — fix **Settings**, then press **Rebuild & run**; you do not need to regenerate the tests. |
| First page is very slow after a start | Normal (10–25 s); the engine loads once. |
| Local model is very slow or the GPU memory is full | Use the `-ctx16384` model variants (see [providers.md](providers.md#local-models-cap-the-context-window-8-gb-gpus)). |
| A model returns an empty answer | A reasoning model used all tokens thinking: pick a non-reasoning model, or raise the token limit in the AI monitor chat. |
| Cloud: **429** | The free model is rate-limited right now — try another model or wait; **Probe free models** marks it ⚠️. |
| Cloud: **404 / 410** | The model is no longer hosted (common on NVIDIA's list) — pick a ✅ one. |
| Cloud: **402 / 💲** | The model is not in the free plan (Ollama Cloud, some OpenRouter models). |
| Coverage / report buttons do nothing | Reload with Ctrl+F5 after an update. Reports are served from `http://localhost:8502`; if that port is busy the app uses the next free one. |
| Icons show words like `arrow_right` | Hard-reload the page (Ctrl+F5). |
| Page goes blank after a long idle | Reload the page; a running job keeps running in the background. |
| All AI tests quarantined, only smoke test passed | Normal for small local models. Try a bigger model or a cloud model on the *Test generator* stage, and compare runs on **Runs & reports**. |
| Build ⚠️ but tests pass | Quarantined files or the smoke-test fallback — read the notes under the result cards. |

**Limits to keep in mind:** results come from AI models and need an engineer's review; nothing here is ISO 26262 /
ASIL qualified; small local models often produce tests that do not compile on the first try (that is why the fix loop,
quarantine and smoke test exist).
