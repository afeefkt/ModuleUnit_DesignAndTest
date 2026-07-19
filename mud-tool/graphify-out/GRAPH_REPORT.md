# Graph Report - moduleunitdesign  (2026-05-22)

## Corpus Check
- 96 files · ~153,845 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1886 nodes · 10898 edges · 45 communities detected
- Extraction: 22% EXTRACTED · 78% INFERRED · 0% AMBIGUOUS · INFERRED: 8449 edges (avg confidence: 0.52)
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
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]

## God Nodes (most connected - your core abstractions)
1. `Settings` - 457 edges
2. `GenerationResult` - 445 edges
3. `ActivityDiagram` - 351 edges
4. `DiagramType` - 326 edges
5. `SequenceDiagram` - 239 edges
6. `Requirement` - 217 edges
7. `MermaidExporter` - 203 edges
8. `ClassDiagram` - 188 edges
9. `StateMachineDiagram` - 186 edges
10. `ActivityNodeType` - 186 edges

## Surprising Connections (you probably didn't know these)
- `Settings` --uses--> `Configuration management for MUD Tool.`  [INFERRED]
  python-sidecar\src\mudtool\config\settings.py → python-sidecar\src\mudtool\config\__init__.py
- `Requirement` --calls--> `test_elaboration_quality_gate_invalid_when_parse_failed()`  [INFERRED]
  python-sidecar\src\mudtool\models\requirements.py → python-sidecar\tests\test_elaborator_enhanced.py
- `Requirement` --calls--> `test_elaboration_quality_score_uses_coverage()`  [INFERRED]
  python-sidecar\src\mudtool\models\requirements.py → python-sidecar\tests\test_elaborator_enhanced.py
- `RequirementSet` --calls--> `sample_requirement_set()`  [INFERRED]
  python-sidecar\src\mudtool\models\requirements.py → python-sidecar\tests\conftest.py
- `AUTOSARValidator` --calls--> `validator()`  [INFERRED]
  python-sidecar\src\mudtool\validation\autosar_validator.py → python-sidecar\tests\unit\test_validation.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (347): ActivityPipeline, AIResponse, BaseAIBackend, Response from an AI backend., Abstract base class for AI inference backends., Chunked Requirement Elaboration for Small Models (2–3B parameters).  Instead of, Extract the first valid JSON array or object from model output., Build (system, user) prompts for SWC identification. (+339 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (157): BaseModel, Enum, AUTOSARMapper, AUTOSAR Mapper - enriches generic UML elements with AUTOSAR semantics.  Stage 4, Map state machine elements to AUTOSAR mode management., Map class diagram elements to AUTOSAR SWCs., Map component diagram elements to AUTOSAR architecture., Ensure SWC name follows AUTOSAR convention: SWC_PascalCase. (+149 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (158): ChunkedElaborator, RequirementElaborator, GuidelinesReader, Delete all cached chunk JSON files. Returns count of files deleted., Reads, chunks, embeds, caches, and retrieves design guideline documents.      Us, ModulePlanner, Analyses architectural requirements and returns a list of SWC modules.      Uses, Args:             orchestrator: An initialised AIOrchestrator instance, used to (+150 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (16): SidecarClient, MUDToolConfig, DiagramGenerator, RequirementBrowser, count(), MUDToolModule, TraceabilityMatrix, MUDToolWorkflow (+8 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (88): _ActivityGraphBuilder, build_mud_activity_context(), _classify_step_kind(), _compact_step_label(), _contains_structural_hint(), _count_helper_calls(), _expand_numbered_step_block(), _extract_helper_call() (+80 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (57): Parse document → list of (section_title, text) pairs., Extract sections from HTML by walking h1/h2/h3 heading tags., Extract sections from PDF using pypdf., Extract sections from DOCX using python-docx., Extract sections from Excel by treating each sheet as a section.          Each r, Extract sections from TXT/MD by Markdown headings or paragraph breaks., _build_evidence_summary(), _combine_module_info() (+49 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (75): _assemble_markdown(), _extract_json(), _fmt_range_unit(), _format_hints_block(), _load_reference(), MudSpecPipeline, Two-stage MUD spec generation pipeline.  Replaces single-pass generation with a, Deterministic cross-reference validation.      Returns a list of human-readable (+67 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (33): ABC, Base AI backend interface., BaseImporter, BaseImporter, ImportResult, success(), CSVImporter, CSV requirement importer. (+25 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (22): create_app(), Create and configure the FastAPI application., Traceability store - requirement-to-model element mapping with provenance., TraceabilityStore, TraceLink, api_client(), _complete_event_payload(), _DummyMapper (+14 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (59): merge_pipeline_results(), get_mapper(), get_orchestrator(), get_render_service(), get_trace_store(), get_validator(), Dependency injection for FastAPI - singleton service instances., Reset the AI orchestrator so it picks up new settings on next use.      Called b (+51 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (42): _diagram_has_cfg_breakage(), _ensure_helper_subdiagrams(), _extract_assumptions(), _extract_json(), _finalize_cfg_fallback(), _normalize_activity_semantics(), _overlay_ai_on_cfg(), Multi-stage activity-diagram generation pipeline.  Mirrors the design of ``mud_p (+34 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (22): build_enriched_context(), _compute_hash(), get_cache_path(), _load_prompt(), _purge_stale_cache(), _active_provider_model(), _collect_covered_reqs(), _count_result_nodes() (+14 more)

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (21): _adaptive_temperature(), _build_critique_system_prompt(), _build_critique_user_prompt(), _build_refinement_user_prompt(), CritiqueResult, _parse_critique_response(), _TemporaryModelOverride, Visual QA Agent - local multimodal LLM review of rendered diagrams.  Pipeline (+13 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (16): _cosine_similarity(), DocumentChunk, GuidelinesStatus, Guidelines RAG - reads design-standard documents and injects relevant chunks int, Scan guidelines_dir, parse docs, embed chunks (or fallback), cache results., Retrieve top-N most relevant chunks and return a Markdown context block., Fast status scan (no embedding load). For the /guidelines/status endpoint., SHA-256 of first 64KB of file (fast, sufficient for cache keying). (+8 more)

### Community 14 - "Community 14"
Cohesion: 0.2
Nodes (11): _assemble(), _compute_hash(), _extract_json(), _fallback_ports(), _fallback_runnables(), _fallback_swc_list(), get_cache_path(), _purge_stale_cache() (+3 more)

### Community 15 - "Community 15"
Cohesion: 0.36
Nodes (1): TestParseResponseWrapper

### Community 16 - "Community 16"
Cohesion: 0.2
Nodes (6): Render all diagrams in a generation result to image files.          Args:, Render via Kroki.io REST API (POST method with JSON body)., Render diagram text via Kroki.io REST API (POST method with JSON body)., Render using a local plantuml.jar subprocess., Render PlantUML text to SVG bytes.          Uses local plantuml.jar if configure, Render PlantUML text to PNG bytes.

### Community 17 - "Community 17"
Cohesion: 0.22
Nodes (5): PreCheckResult, Structural Pre-Check - runs BEFORE the AI draft stage.  Analyses the requireme, Run pre-check for a given diagram type.          Returns a PreCheckResult with, Outcome of a structural pre-check pass for one diagram type., Format gaps as a hint block for injection into the generation prompt.

### Community 18 - "Community 18"
Cohesion: 0.39
Nodes (8): convert(), _format_calib_example(), _format_port_example(), _format_runnable_example(), main(), print_summary(), Convert EPS_MUD_Enhanced.csv (19-column tabular MUD spec) to a structured JSON r, read_csv()

### Community 19 - "Community 19"
Cohesion: 0.36
Nodes (7): _deepseek_orchestrator(), test_deepseek_activity_override_updates_deepseek_model(), test_deepseek_local_r1_alias_maps_to_hosted_reasoner(), test_deepseek_reviewer_override_updates_deepseek_model(), test_deepseek_skeleton_override_updates_deepseek_model(), test_local_ollama_ignores_hosted_deepseek_reviewer_alias(), test_local_ollama_keeps_real_local_deepseek_r1_tag()

### Community 21 - "Community 21"
Cohesion: 0.33
Nodes (3): Filter requirements by type., Get all functional requirements., Get all interface requirements.

### Community 22 - "Community 22"
Cohesion: 0.4
Nodes (5): Web UI FastAPI router.  Serves the built-in browser dashboard at GET /. All diag, Read an HTML template file., Serve the built-in MUD Tool Web UI dashboard., _read_template(), web_ui()

### Community 23 - "Community 23"
Cohesion: 0.4
Nodes (1): Scan node names for MISRA-C Hungarian variable patterns and return (type, name)

### Community 24 - "Community 24"
Cohesion: 0.4
Nodes (1): Validation result models.

### Community 25 - "Community 25"
Cohesion: 0.5
Nodes (3): _encode_plantuml(), Diagram render service — converts PlantUML text to SVG/PNG images.  Two renderin, Encode PlantUML text for Kroki.io URL/body (deflate + base64 variant).

### Community 26 - "Community 26"
Cohesion: 0.83
Nodes (3): _read_jsonl(), test_run_debug_trace_recreates_latest_file_each_run(), test_run_debug_trace_summarizes_large_payloads_and_redacts_secrets()

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): MUD Tool - AI-Assisted AUTOSAR Module & Unit Design Tool.

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Check backend health status.

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): JSON schemas for per-element MUD spec generation.  Each schema is passed as the

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): FastAPI routes and API definitions.

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Configuration management for MUD Tool.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Utility functions for the MUD Tool.

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): MUD Tool built-in Web UI.  Served at http://127.0.0.1:8042/ — a zero-install bro

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Return backend identifier (e.g., 'anthropic', 'local').

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Check if this backend is ready for inference.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Generate a completion.          Args:             system_prompt: System/context

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Generate a streaming completion.          Yields partial text chunks as they arr

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Pure-Python cosine similarity.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Token intersection ratio (Jaccard-like) for keyword fallback.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Accept LLM variants: 'type'/'nodeType' → 'node_type', strip suffixes.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Accept LLM variants: 'from'→'source', 'to'→'target', 'source_id'→'source'.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Extract JSON from the AI response and build PlanResult.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Locate the .env file relative to this settings module, regardless of CWD.      T

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Application settings loaded from environment variables and .env file.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Get cached application settings singleton.

## Knowledge Gaps
- **139 isolated node(s):** `Per-run structured debug trace for UI-triggered generation workflows.`, `JSONL debug trace that is recreated at the start of each UI run.`, `MUD Tool Sidecar - FastAPI application entry point.  Runs as a localhost HTTP se`, `Configure application logging.`, `Application lifespan: startup and shutdown.` (+134 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 15`** (15 nodes): `TestParseResponseWrapper`, `._fake_response()`, `._make_orchestrator()`, `.test_flat_format_still_works()`, `.test_wrapper_accepts_edge_source_target_id_aliases()`, `.test_wrapper_accepts_legacy_activity_shape()`, `.test_wrapper_camel_case_node_type_is_supported()`, `.test_wrapper_format_extracted()`, `.test_wrapper_infers_and_defaults_node_type_with_warning()`, `.test_wrapper_legacy_activity_missing_name_is_derived()`, `.test_wrapper_multiple_diagrams()`, `.test_wrapper_no_longer_creates_empty_diagram()`, `.test_wrapper_normalizes_subdiagram_edge_aliases()`, `.test_wrapper_null_node_type_uses_legacy_type()`, `.test_wrapper_sanitizes_mud_style_node_ids()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (5 nodes): `.export_diagram()`, `.export_result()`, `._extract_variables()`, `._walk_node()`, `Scan node names for MISRA-C Hungarian variable patterns and return (type, name)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (5 nodes): `error_count()`, `info_count()`, `Validation result models.`, `warning_count()`, `validation.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (2 nodes): `MUD Tool - AI-Assisted AUTOSAR Module & Unit Design Tool.`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (2 nodes): `.health_check()`, `Check backend health status.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (2 nodes): `JSON schemas for per-element MUD spec generation.  Each schema is passed as the`, `mud_element_schemas.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (2 nodes): `FastAPI routes and API definitions.`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (2 nodes): `Configuration management for MUD Tool.`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (2 nodes): `__init__.py`, `Utility functions for the MUD Tool.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (2 nodes): `__init__.py`, `MUD Tool built-in Web UI.  Served at http://127.0.0.1:8042/ — a zero-install bro`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Return backend identifier (e.g., 'anthropic', 'local').`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Check if this backend is ready for inference.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Generate a completion.          Args:             system_prompt: System/context`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Generate a streaming completion.          Yields partial text chunks as they arr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Pure-Python cosine similarity.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Token intersection ratio (Jaccard-like) for keyword fallback.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Accept LLM variants: 'type'/'nodeType' → 'node_type', strip suffixes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Accept LLM variants: 'from'→'source', 'to'→'target', 'source_id'→'source'.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Extract JSON from the AI response and build PlanResult.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Locate the .env file relative to this settings module, regardless of CWD.      T`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Application settings loaded from environment variables and .env file.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Get cached application settings singleton.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 0` to `Community 1`, `Community 2`, `Community 33`, `Community 5`, `Community 8`, `Community 9`, `Community 12`, `Community 15`, `Community 16`, `Community 19`, `Community 25`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Why does `GenerationResult` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 8`, `Community 9`, `Community 11`, `Community 12`, `Community 15`, `Community 16`, `Community 25`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `ValidationReport` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 5`, `Community 8`, `Community 24`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Are the 447 inferred relationships involving `Settings` (e.g. with `ChunkedElaborator` and `Chunked Requirement Elaboration for Small Models (2–3B parameters).  Instead of`) actually correct?**
  _`Settings` has 447 INFERRED edges - model-reasoned connections that need verification._
- **Are the 442 inferred relationships involving `GenerationResult` (e.g. with `AIOrchestrator` and `AI Orchestrator - routes requests to local or cloud backend.  Manages prompt ren`) actually correct?**
  _`GenerationResult` has 442 INFERRED edges - model-reasoned connections that need verification._
- **Are the 348 inferred relationships involving `ActivityDiagram` (e.g. with `ActivityPipeline` and `Multi-stage activity-diagram generation pipeline.  Mirrors the design of ``mud_p`) actually correct?**
  _`ActivityDiagram` has 348 INFERRED edges - model-reasoned connections that need verification._
- **Are the 322 inferred relationships involving `DiagramType` (e.g. with `ActivityPipeline` and `Multi-stage activity-diagram generation pipeline.  Mirrors the design of ``mud_p`) actually correct?**
  _`DiagramType` has 322 INFERRED edges - model-reasoned connections that need verification._