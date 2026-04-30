# Graph Report - moduleunitdesign  (2026-04-29)

## Corpus Check
- 89 files · ~137,864 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1631 nodes · 8324 edges · 33 communities detected
- Extraction: 27% EXTRACTED · 73% INFERRED · 0% AMBIGUOUS · INFERRED: 6076 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]

## God Nodes (most connected - your core abstractions)
1. `GenerationResult` - 358 edges
2. `Settings` - 331 edges
3. `ActivityDiagram` - 255 edges
4. `DiagramType` - 242 edges
5. `SequenceDiagram` - 203 edges
6. `Requirement` - 165 edges
7. `ClassDiagram` - 152 edges
8. `StateMachineDiagram` - 150 edges
9. `ComponentDiagram` - 148 edges
10. `ActivityNodeType` - 147 edges

## Surprising Connections (you probably didn't know these)
- `Mermaid Syntax Linter - validates generated Mermaid text before export.  Pure` --uses--> `DiagramType`  [INFERRED]
  python-sidecar\src\mudtool\validation\mermaid_linter.py → python-sidecar\src\mudtool\models\json_uml.py
- `Result of a Mermaid syntax lint pass.` --uses--> `DiagramType`  [INFERRED]
  python-sidecar\src\mudtool\validation\mermaid_linter.py → python-sidecar\src\mudtool\models\json_uml.py
- `Validates and auto-corrects Mermaid diagram text.      Checks:       - Correc` --uses--> `DiagramType`  [INFERRED]
  python-sidecar\src\mudtool\validation\mermaid_linter.py → python-sidecar\src\mudtool\models\json_uml.py
- `Lint Mermaid text for a given diagram type.          Always returns a LintResu` --uses--> `DiagramType`  [INFERRED]
  python-sidecar\src\mudtool\validation\mermaid_linter.py → python-sidecar\src\mudtool\models\json_uml.py
- `Lint all diagrams in a key→mermaid_text dict.          diagram_type_map maps k` --uses--> `DiagramType`  [INFERRED]
  python-sidecar\src\mudtool\validation\mermaid_linter.py → python-sidecar\src\mudtool\models\json_uml.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (226): BaseModel, Enum, AUTOSARMapper, AUTOSAR Mapper - enriches generic UML elements with AUTOSAR semantics.  Stage 4, Map state machine elements to AUTOSAR mode management., Map class diagram elements to AUTOSAR SWCs., Map component diagram elements to AUTOSAR architecture., Ensure SWC name follows AUTOSAR convention: SWC_PascalCase. (+218 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (195): ActivityPipeline, Multi-stage activity-diagram generation pipeline.  Mirrors the design of ``mud_p, Apply reviewer patches deterministically + stamp provenance., Repair / drop edges whose source/target don't match any node id, then     auto-f, Merge AI-enriched content (names, guards, rte metadata) onto the         determi, 5-stage activity flowchart generator.      Mirrors :class:`mudtool.ai.mud_pipeli, Run all 5 stages and return validated diagram dicts.          Returns an empty l, Fall-back: build skeleton entries from the parsed MUD context. (+187 more)

### Community 2 - "Community 2"
Cohesion: 0.02
Nodes (96): ABC, Base AI backend interface., Elaborates requirements via small, reliable, chunked AI calls.      Produces the, build_enriched_context(), _compute_hash(), get_cache_path(), _load_prompt(), Requirement Elaboration with AI Chain-of-Thought Reasoning.  Pre-processes raw r (+88 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (156): ChunkedElaborator, RequirementElaborator, GuidelinesReader, Delete all cached chunk JSON files. Returns count of files deleted., Reads, chunks, embeds, caches, and retrieves design guideline documents.      Us, ModulePlanner, Analyses architectural requirements and returns a list of SWC modules.      Uses, Args:             orchestrator: An initialised AIOrchestrator instance, used to (+148 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (13): SidecarClient, MUDToolConfig, DiagramGenerator, RequirementBrowser, count(), MUDToolModule, TraceabilityMatrix, MUDToolWorkflow (+5 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (56): Parse document → list of (section_title, text) pairs., Extract sections from HTML by walking h1/h2/h3 heading tags., Extract sections from PDF using pypdf., Extract sections from DOCX using python-docx., Extract sections from Excel by treating each sheet as a section.          Each r, Extract sections from TXT/MD by Markdown headings or paragraph breaks., _build_evidence_summary(), _combine_module_info() (+48 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (60): _assemble_markdown(), _extract_json(), _fmt_range_unit(), _format_hints_block(), _load_reference(), MudSpecPipeline, Two-stage MUD spec generation pipeline.  Replaces single-pass generation with a, Deterministic cross-reference validation.      Returns a list of human-readable (+52 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (63): _ActivityGraphBuilder, build_mud_activity_context(), _classify_step_kind(), _compact_step_label(), _contains_structural_hint(), _count_helper_calls(), _expand_numbered_step_block(), _extract_helper_call() (+55 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (16): Clean shutdown of all services., shutdown_services(), _find_env_file(), Application settings and configuration., Locate the .env file relative to this settings module, regardless of CWD.      T, lifespan(), main(), MUD Tool Sidecar - FastAPI application entry point.  Runs as a localhost HTTP se (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (16): _cosine_similarity(), DocumentChunk, GuidelinesStatus, Guidelines RAG - reads design-standard documents and injects relevant chunks int, Scan guidelines_dir, parse docs, embed chunks (or fallback), cache results., Retrieve top-N most relevant chunks and return a Markdown context block., Fast status scan (no embedding load). For the /guidelines/status endpoint., SHA-256 of first 64KB of file (fast, sufficient for cache keying). (+8 more)

### Community 10 - "Community 10"
Cohesion: 0.11
Nodes (20): _assemble(), _compute_hash(), _extract_json(), _fallback_ports(), _fallback_runnables(), _fallback_swc_list(), get_cache_path(), Chunked Requirement Elaboration for Small Models (2–3B parameters).  Instead of (+12 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (7): _adaptive_temperature(), _build_critique_system_prompt(), _build_critique_user_prompt(), _build_refinement_user_prompt(), merge_pipeline_results(), StageResult, _TemporaryModelOverride

### Community 12 - "Community 12"
Cohesion: 0.36
Nodes (1): TestParseResponseWrapper

### Community 13 - "Community 13"
Cohesion: 0.27
Nodes (8): _diagram_has_cfg_breakage(), _extract_json(), _finalize_cfg_fallback(), _overlay_ai_on_cfg(), _scrub_orphan_edges(), _stage2_xref(), _stage5_finalise(), _synthesise_skeleton()

### Community 14 - "Community 14"
Cohesion: 0.21
Nodes (2): _replace_diagram(), VisualQAResult

### Community 15 - "Community 15"
Cohesion: 0.39
Nodes (8): convert(), _format_calib_example(), _format_port_example(), _format_runnable_example(), main(), print_summary(), Convert EPS_MUD_Enhanced.csv (19-column tabular MUD spec) to a structured JSON r, read_csv()

### Community 16 - "Community 16"
Cohesion: 0.25
Nodes (4): Export all ActivityDiagrams in a GenerationResult.          Returns: {diagram_na, Recursively walk the node graph and emit C code., Scan node names for MISRA-C Hungarian variable patterns and return (type, name), Generate C skeleton code for a single ActivityDiagram.

### Community 17 - "Community 17"
Cohesion: 0.33
Nodes (4): LintResult, Mermaid Syntax Linter - validates generated Mermaid text before export.  Pure, # IMPORTANT: the arrow character class is [->]+ (NOT [->|]+)., Result of a Mermaid syntax lint pass.

### Community 18 - "Community 18"
Cohesion: 0.4
Nodes (5): Web UI FastAPI router.  Serves the built-in browser dashboard at GET /. All diag, Read an HTML template file., Serve the built-in MUD Tool Web UI dashboard., _read_template(), web_ui()

### Community 19 - "Community 19"
Cohesion: 0.4
Nodes (1): Validation result models.

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): MUD Tool - AI-Assisted AUTOSAR Module & Unit Design Tool.

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): JSON schemas for per-element MUD spec generation.  Each schema is passed as the

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): FastAPI routes and API definitions.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Utility functions for the MUD Tool.

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): MUD Tool built-in Web UI.  Served at http://127.0.0.1:8042/ — a zero-install bro

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Return backend identifier (e.g., 'anthropic', 'local').

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Check if this backend is ready for inference.

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Generate a completion.          Args:             system_prompt: System/context

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Generate a streaming completion.          Yields partial text chunks as they arr

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Pure-Python cosine similarity.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Token intersection ratio (Jaccard-like) for keyword fallback.

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Accept LLM variants: 'type'/'nodeType' → 'node_type', strip suffixes.

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Accept LLM variants: 'from'→'source', 'to'→'target', 'source_id'→'source'.

## Knowledge Gaps
- **133 isolated node(s):** `MUD Tool Sidecar - FastAPI application entry point.  Runs as a localhost HTTP se`, `Configure application logging.`, `Application lifespan: startup and shutdown.`, `Create and configure the FastAPI application.`, `CLI entry point for the sidecar server.` (+128 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 12`** (15 nodes): `TestParseResponseWrapper`, `._fake_response()`, `._make_orchestrator()`, `.test_flat_format_still_works()`, `.test_wrapper_accepts_edge_source_target_id_aliases()`, `.test_wrapper_accepts_legacy_activity_shape()`, `.test_wrapper_camel_case_node_type_is_supported()`, `.test_wrapper_format_extracted()`, `.test_wrapper_infers_and_defaults_node_type_with_warning()`, `.test_wrapper_legacy_activity_missing_name_is_derived()`, `.test_wrapper_multiple_diagrams()`, `.test_wrapper_no_longer_creates_empty_diagram()`, `.test_wrapper_normalizes_subdiagram_edge_aliases()`, `.test_wrapper_null_node_type_uses_legacy_type()`, `.test_wrapper_sanitizes_mud_style_node_ids()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (13 nodes): `has_issues()`, `_replace_diagram()`, `.run()`, `.analyze_mermaid()`, `._build_vision_prompt()`, `._call_vision_model()`, `._parse_vision_response()`, `._render_png()`, `.run_visual_qa_pass()`, `VisualQAResult`, `.to_correction_prompt_block()`, `.to_summary()`, `visual_qa.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (5 nodes): `error_count()`, `info_count()`, `Validation result models.`, `warning_count()`, `validation.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (2 nodes): `MUD Tool - AI-Assisted AUTOSAR Module & Unit Design Tool.`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (2 nodes): `JSON schemas for per-element MUD spec generation.  Each schema is passed as the`, `mud_element_schemas.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (2 nodes): `FastAPI routes and API definitions.`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (2 nodes): `__init__.py`, `Utility functions for the MUD Tool.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (2 nodes): `__init__.py`, `MUD Tool built-in Web UI.  Served at http://127.0.0.1:8042/ — a zero-install bro`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Return backend identifier (e.g., 'anthropic', 'local').`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Check if this backend is ready for inference.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Generate a completion.          Args:             system_prompt: System/context`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Generate a streaming completion.          Yields partial text chunks as they arr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Pure-Python cosine similarity.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Token intersection ratio (Jaccard-like) for keyword fallback.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Accept LLM variants: 'type'/'nodeType' → 'node_type', strip suffixes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Accept LLM variants: 'from'→'source', 'to'→'target', 'source_id'→'source'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ValidationReport` connect `Community 3` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 19`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Why does `Settings` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 8`, `Community 10`, `Community 11`, `Community 12`, `Community 14`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Why does `GenerationResult` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 7`, `Community 8`, `Community 11`, `Community 12`, `Community 14`, `Community 16`?**
  _High betweenness centrality (0.122) - this node is a cross-community bridge._
- **Are the 355 inferred relationships involving `GenerationResult` (e.g. with `AIOrchestrator` and `AI Orchestrator - routes requests to local or cloud backend.  Manages prompt ren`) actually correct?**
  _`GenerationResult` has 355 INFERRED edges - model-reasoned connections that need verification._
- **Are the 321 inferred relationships involving `Settings` (e.g. with `ChunkedElaborator` and `Chunked Requirement Elaboration for Small Models (2–3B parameters).  Instead of`) actually correct?**
  _`Settings` has 321 INFERRED edges - model-reasoned connections that need verification._
- **Are the 252 inferred relationships involving `ActivityDiagram` (e.g. with `ActivityPipeline` and `Multi-stage activity-diagram generation pipeline.  Mirrors the design of ``mud_p`) actually correct?**
  _`ActivityDiagram` has 252 INFERRED edges - model-reasoned connections that need verification._
- **Are the 238 inferred relationships involving `DiagramType` (e.g. with `ActivityPipeline` and `Multi-stage activity-diagram generation pipeline.  Mirrors the design of ``mud_p`) actually correct?**
  _`DiagramType` has 238 INFERRED edges - model-reasoned connections that need verification._