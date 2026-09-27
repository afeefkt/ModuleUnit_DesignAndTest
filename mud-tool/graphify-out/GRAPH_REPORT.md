# Graph Report - mud-tool  (2026-09-27)

## Corpus Check
- 131 files · ~198,003 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 4292 nodes · 17195 edges · 187 communities (135 shown, 52 thin omitted)
- Extraction: 42% EXTRACTED · 58% INFERRED · 0% AMBIGUOUS · INFERRED: 10017 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e257b379`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ActivityDiagram
- Message
- RequirementSet
- MUDToolConfig
- mud_activity_context.py
- module_planner.py
- mud_pipeline_stages.py
- ImportResult
- TraceLink
- routes.py
- DiagramType
- .generate_diagram
- pipeline.py
- .load_all
- chunked_elaborator.py
- TestParseResponseWrapper
- PlantUMLExporter
- routes.py
- csv_to_reference_json.py
- test_orchestrator_model_overrides.py
- .get_by_type
- app.py
- .export_diagram
- ActivityDiagram
- GenerationResult
- test_debug_trace.py
- Settings
- MUD Tool - AI-Assisted AUTOSAR Module & Unit Design Tool.
- StructuralValidator
- JSON schemas for per-element MUD spec generation.  Each schema is passed as the
- FastAPI routes and API definitions.
- GenerationResult
- utils/__init__.py
- web/__init__.py
- Return backend identifier (e.g., 'anthropic', 'local').
- Check if this backend is ready for inference.
- Generate a completion.          Args:             system_prompt: System/context
- Generate a streaming completion.          Yields partial text chunks as they arr
- Pure-Python cosine similarity.
- Token intersection ratio (Jaccard-like) for keyword fallback.
- Accept LLM variants: 'type'/'nodeType' → 'node_type', strip suffixes.
- Accept LLM variants: 'from'→'source', 'to'→'target', 'source_id'→'source'.
- Extract JSON from the AI response and build PlanResult.
- Locate the .env file relative to this settings module, regardless of CWD.      T
- Application settings loaded from environment variables and .env file.
- Get cached application settings singleton.
- Requirement
- json_uml.py
- Settings
- models/__init__.py
- AIOrchestrator
- module_planner.py
- GuidelinesReader
- ValidationReport
- ActivityPipeline
- AUTOSAR MUD Skill — APPENDIX (Reference Only)
- mud_activity_context.py
- mud_spec_generator.py
- mud_pipeline_stages.py
- MermaidExporter
- TraceabilityStore
- STEP 5 — MERMAID GENERATION ALGORITHM
- MUDToolConfig
- CloudBackend
- TestParseResponseWrapper
- ImportResult
- .map_diagram
- $defs
- _uid
- MudSpecPipeline
- properties
- properties
- properties
- MudActivityContext
- MUD Tool — AI-Assisted AUTOSAR Module & Unit Design
- build_mud_activity_context
- section7_normalizer.py
- main.py
- .export_diagram
- TestLiveExportEndpoints
- Message
- str
- properties
- RequirementBrowser
- build_mud_activity_context
- Section7NormalizationResult
- TestGuidelineConstants
- diagnose_eps_flowchart_pipeline.py
- activity_pipeline_stages.py
- SidecarClient
- properties
- section7_normalizer.py
- conftest.py
- SidecarClient
- properties
- diagnose_eps_flowchart_pipeline.py
- properties
- RequirementBrowser
- _ActivityGraphBuilder
- .export_diagram
- .export_diagram
- debug_trace.py
- com.fasterxml.jackson.databind.JsonNode
- MUDToolModule
- MarkdownImporter
- TestPromptContract
- test_module_planner.py
- Current Implementation Architecture (Updated)
- mud_spec_generator.py
- review_issue_fingerprint
- TestBuildSignalTable
- test_c_skeleton_exporter.py
- .render_all
- ._check_state_machine_owners
- _FakeBackend
- ._extract_text
- Clean shutdown of all services.
- enum
- .executeRequest
- ValidationPanel
- TestBuildIrvCoherenceBlock
- ._parse_response
- ReviewIssue
- PMSM_FOC_Architecture_Requirements_6d06e0b3.md
- ._parse_review
- .import_file
- TextImporter
- _uid
- TraceabilityMatrix
- ._build_requirement
- CSVImporter
- csv_to_reference_json.py
- drawio_exporter.py
- ValidationPanel
- _safe_json_value
- _ActivityLayoutBox
- normalize_section7_markdown
- Lifeline
- DiagramGenerator
- ExcelImporter
- _EmptyReviewBackend
- Troubleshooting
- .regenerate_spec
- Design Guidelines Folder
- TraceabilityMatrix
- TestAutoRepairGate
- ._repair_section7_prose
- ValidationSeverity
- _EmptyReviewBackend
- 4. AI subsystem architecture
- .import_file
- MUD Tool Test Strategy
- test_framework_contract.py
- 6. Activity / flowchart architecture
- REST API
- Requirement File Formats
- Installation
- bms_requirements_d466eeee.md
- 7. Data model and validation architecture
- Hardware Requirements
- run_tests.sh
- .clear_cache
- .__init__
- CLAUDE.md
- .get_by_id
- .get_by_module_hint
- ._detect_column
- .__init__
- Association
- ClassAttribute
- utils/__init__.py
- web/__init__.py
- .validator
- .test_requirement_coverage
- run.sh
- setup.sh
- com.mudtool:mud-tool-modelio-plugin
- mudtool

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
- `_parse_numbered_step_entries()` --calls--> `test_parse_numbered_step_entries_expands_c_style_pseudocode_blocks()`  [INFERRED]
  python-sidecar/src/mudtool/ai/mud_activity_context.py → python-sidecar/tests/unit/test_mud_activity_context.py
- `deterministic_requirement_coverage()` --calls--> `test_deterministic_coverage_detects_explicit_section7_trace()`  [INFERRED]
  python-sidecar/src/mudtool/ai/mud_spec_generator.py → python-sidecar/tests/unit/test_mud_spec_patch_only.py
- `Requirement` --calls--> `test_elaboration_quality_gate_invalid_when_parse_failed()`  [INFERRED]
  python-sidecar/src/mudtool/models/requirements.py → python-sidecar/tests/test_elaborator_enhanced.py
- `Requirement` --calls--> `test_elaboration_quality_score_uses_coverage()`  [INFERRED]
  python-sidecar/src/mudtool/models/requirements.py → python-sidecar/tests/test_elaborator_enhanced.py
- `TraceabilityStore` --calls--> `store()`  [INFERRED]
  python-sidecar/src/mudtool/traceability/store.py → python-sidecar/tests/unit/test_traceability.py

## Import Cycles
- None detected.

## Communities (187 total, 52 thin omitted)

### Community 0 - "ActivityDiagram"
Cohesion: 0.09
Nodes (128): ActivityPipeline, AIResponse, Response from an AI backend., CloudBackend, AI Engine - Orchestrator, Prompt Engine, and inference backends., LocalBackend, Helpers for building MUD-first activity-generation context., # IMPORTANT: keep newlines intact — Section 7 pseudo-code is multi-line (+120 more)

### Community 1 - "Message"
Cohesion: 0.06
Nodes (83): BaseModel, Enum, AUTOSARMapper, AUTOSAR Mapper - enriches generic UML elements with AUTOSAR semantics.  Stage 4, Map state machine elements to AUTOSAR mode management., Map class diagram elements to AUTOSAR SWCs., Map component diagram elements to AUTOSAR architecture., Ensure SWC name follows AUTOSAR convention: SWC_PascalCase. (+75 more)

### Community 2 - "RequirementSet"
Cohesion: 0.20
Nodes (124): ChunkedElaborator, RequirementElaborator, GuidelinesReader, Reads, chunks, embeds, caches, and retrieves design guideline documents.      Us, ModulePlanner, Analyses architectural requirements and returns a list of SWC modules.      Uses, MudSpecGenerator, SpecReviewResult (+116 more)

### Community 4 - "mud_activity_context.py"
Cohesion: 0.18
Nodes (22): _classify_step_kind(), _compact_step_label(), _contains_structural_hint(), _count_helper_calls(), _expand_numbered_step_block(), _extract_helper_call(), _extract_section(), has_structured_flow_source() (+14 more)

### Community 5 - "module_planner.py"
Cohesion: 0.19
Nodes (25): _combine_module_info(), _dedupe_preserve_order(), _default_module_description(), _derive_complexity(), _derive_description_from_titles(), _derive_modules_from_free_text(), _derive_modules_from_requirements_text(), _extract_req_ids() (+17 more)

### Community 6 - "mud_pipeline_stages.py"
Cohesion: 0.10
Nodes (19): _assemble_markdown(), _extract_json(), _fmt_range_unit(), _format_hints_block(), _load_reference(), Two-stage MUD spec generation pipeline.  Replaces single-pass generation with a, Deterministic cross-reference validation.      Returns a list of human-readable, Assemble the 7-section MUD spec Markdown from validated skeleton + section-7 dat (+11 more)

### Community 7 - "ImportResult"
Cohesion: 0.05
Nodes (32): ABC, Base AI backend interface., BaseImporter, BaseImporter, ImportResult, CSVImporter, CSV requirement importer., Import requirements from CSV files.      Same column structure as Excel template (+24 more)

### Community 8 - "TraceLink"
Cohesion: 0.05
Nodes (25): create_app(), Create and configure the FastAPI application., Traceability store - requirement-to-model element mapping with provenance., A single traceability link between a requirement and a model element., TraceLink, api_client(), _complete_event_payload(), _DummyMapper (+17 more)

### Community 9 - "routes.py"
Cohesion: 0.08
Nodes (53): get_mapper(), get_orchestrator(), get_render_service(), get_trace_store(), get_validator(), reset_orchestrator(), accept_element(), analyze_requirements() (+45 more)

### Community 10 - "DiagramType"
Cohesion: 0.05
Nodes (62): Multi-stage activity-diagram generation pipeline.  Mirrors the design of ``mud_p, Apply reviewer patches deterministically + stamp provenance., Repair / drop edges whose source/target don't match any node id, then     auto-f, Repair / drop edges whose source/target don't match any node id, then     auto-, Normalize call-node semantics before AUTOSAR validation., Merge AI-enriched content (names, guards, rte metadata) onto the         determi, Stitch orphaned nodes (no incoming edges) into the nearest decision., Ask reviewer for issues + patches.  Returns (patches, issues). (+54 more)

### Community 11 - ".generate_diagram"
Cohesion: 0.07
Nodes (22): build_enriched_context(), _compute_hash(), get_cache_path(), _load_prompt(), _purge_stale_cache(), _active_provider_model(), _collect_covered_reqs(), _count_result_nodes() (+14 more)

### Community 12 - "pipeline.py"
Cohesion: 0.14
Nodes (6): _adaptive_temperature(), _build_critique_system_prompt(), _build_critique_user_prompt(), _build_refinement_user_prompt(), _parse_critique_response(), _TemporaryModelOverride

### Community 13 - ".load_all"
Cohesion: 0.08
Nodes (16): _cosine_similarity(), DocumentChunk, GuidelinesStatus, Guidelines RAG - reads design-standard documents and injects relevant chunks int, Scan guidelines_dir, parse docs, embed chunks (or fallback), cache results., Retrieve top-N most relevant chunks and return a Markdown context block., Fast status scan (no embedding load). For the /guidelines/status endpoint., SHA-256 of first 64KB of file (fast, sufficient for cache keying). (+8 more)

### Community 14 - "chunked_elaborator.py"
Cohesion: 0.20
Nodes (11): _assemble(), _compute_hash(), _extract_json(), _fallback_ports(), _fallback_runnables(), _fallback_swc_list(), get_cache_path(), _purge_stale_cache() (+3 more)

### Community 16 - "PlantUMLExporter"
Cohesion: 0.06
Nodes (18): export_model(), Model generation and AUTOSAR mapping., PlantUMLExporter, _encode_plantuml(), Diagram render service — converts PlantUML text to SVG/PNG images.  Two renderin, Render all diagrams in a generation result to image files.          Args:, Render via Kroki.io REST API (POST method with JSON body)., Render diagram text via Kroki.io REST API (POST method with JSON body). (+10 more)

### Community 17 - "routes.py"
Cohesion: 0.05
Nodes (168): post, Elaborates terse requirements into structured AUTOSAR JSON. Uses chain-of-…, RequirementElaborator, ModulePlanner, Analyses architectural requirements and returns a list of SWC modules. Uses the…, Args: orchestrator: An initialised AIOrchestrator instance, used to access the…, MudSpecGenerator, Generates a Module Unit Design spec Markdown for a single SWC. Usage: gen =… (+160 more)

### Community 18 - "csv_to_reference_json.py"
Cohesion: 0.39
Nodes (8): convert(), _format_calib_example(), _format_port_example(), _format_runnable_example(), main(), print_summary(), Convert EPS_MUD_Enhanced.csv (19-column tabular MUD spec) to a structured JSON r, read_csv()

### Community 19 - "test_orchestrator_model_overrides.py"
Cohesion: 0.70
Nodes (4): _deepseek_orchestrator(), test_deepseek_activity_override_updates_deepseek_model(), test_deepseek_reviewer_override_updates_deepseek_model(), test_deepseek_skeleton_override_updates_deepseek_model()

### Community 21 - ".get_by_type"
Cohesion: 0.33
Nodes (3): Filter requirements by type., Get all functional requirements., Get all interface requirements.

### Community 22 - "app.py"
Cohesion: 0.40
Nodes (5): Web UI FastAPI router.  Serves the built-in browser dashboard at GET /. All diag, Read an HTML template file., Serve the built-in MUD Tool Web UI dashboard., _read_template(), web_ui()

### Community 24 - "ActivityDiagram"
Cohesion: 0.04
Nodes (74): model_validator, AIResponse, BaseModel, Base AI backend interface., Response from an AI backend., Cloud AI backend supporting Anthropic Claude and OpenAI-compatible APIs., Requirement Elaboration with AI Chain-of-Thought Reasoning. Pre-processes raw…, AI Engine - Orchestrator, Prompt Engine, and inference backends. (+66 more)

### Community 25 - "GenerationResult"
Cohesion: 0.05
Nodes (99): Dependency injection for FastAPI - singleton service instances., Reset the AI orchestrator so it picks up new settings on next use.      Called b, C-code skeleton generator from ActivityDiagram JSON.  Walks the node/edge graph, Export all ActivityDiagrams in a GenerationResult.          Returns: {diagram_na, Recursively walk the node graph and emit C code., Export ActivityDiagram JSON to C-code skeleton files., Generate C skeleton code for a single ActivityDiagram., _ActivityLayoutBox (+91 more)

### Community 26 - "test_debug_trace.py"
Cohesion: 0.83
Nodes (3): _read_jsonl(), test_run_debug_trace_recreates_latest_file_each_run(), test_run_debug_trace_summarizes_large_payloads_and_redacts_secrets()

### Community 27 - "Settings"
Cohesion: 0.02
Nodes (119): BaseAIBackend, Abstract base class for AI inference backends., Check backend health status., Chunked Requirement Elaboration for Small Models (2–3B parameters).  Instead of, Extract the first valid JSON array or object from model output., Build (system, user) prompts for SWC identification., Build (system, user) prompts for SWC identification., Build (system, user) prompts for port table generation. (+111 more)

### Community 30 - "StructuralValidator"
Cohesion: 0.08
Nodes (78): Base importer interface and common utilities., Parse requirement type string to enum., Parse ASIL level string to enum., Parse priority string to enum., Parse status string to enum., Build a Requirement from a mapped row dict.          Args:             row_data:, Result of an import operation., Abstract base class for requirement importers. (+70 more)

### Community 33 - "GenerationResult"
Cohesion: 0.04
Nodes (58): Multi-stage activity-diagram generation pipeline. Mirrors the design of…, _build_critique_system_prompt(), _build_critique_user_prompt(), _build_refinement_user_prompt(), CritiqueResult, merge_pipeline_results(), _parse_critique_response(), PipelineGenerationResult (+50 more)

### Community 50 - "Requirement"
Cohesion: 0.04
Nodes (53): ChunkedElaborator, _extract_json(), _fallback_ports(), _fallback_runnables(), _fallback_swc_list(), _purge_stale_cache(), callable, Path (+45 more)

### Community 51 - "json_uml.py"
Cohesion: 0.07
Nodes (61): main(), _print_header(), draw.io XML diagram exporter. Generates .drawio files (diagrams.net XML) that…, PlantUML text exporter for quick previews, diffs, and reviews. Generates…, XMI (UML 2.x) Exporter - converts JSON-UML models to XMI format. XMI is the…, ClassDiagram, ClassElement, ClassOperation (+53 more)

### Community 52 - "Settings"
Cohesion: 0.03
Nodes (42): BaseSettings, _detect_gpu_available(), LocalBackend, Stream generation from local model., Unload the model from memory to free resources., Detect whether a compatible GPU (CUDA or Metal) is available. Checks for: -…, Local LLM inference backend via llama-cpp-python. Manages model loading,…, Load the GGUF model into memory. (+34 more)

### Community 53 - "models/__init__.py"
Cohesion: 0.06
Nodes (60): AUTOSARMapper, AUTOSAR Mapper - enriches generic UML elements with AUTOSAR semantics. Stage 4…, Extract AUTOSAR SWC definitions from generated diagrams., Convert a class element to an ApplicationSWC., Convert a component element to an ApplicationSWC., Infer SWC type from stereotype., Merge source SWC info into target (combine ports, runnables, etc.)., Maps generic UML/JSON-UML elements to AUTOSAR-specific constructs. This mapper… (+52 more)

### Community 54 - "AIOrchestrator"
Cohesion: 0.05
Nodes (42): BaseAIBackend, ABC, Abstract base class for AI inference backends., Return backend identifier (e.g., 'anthropic', 'local')., Check if this backend is ready for inference., Generate a completion. Args: system_prompt: System/context prompt with domain…, Generate a streaming completion. Yields partial text chunks as they arrive., Check backend health status. (+34 more)

### Community 55 - "module_planner.py"
Cohesion: 0.08
Nodes (48): Pattern, _build_evidence_summary(), _combine_module_info(), _consolidate_sub_swcs(), _dedupe_preserve_order(), _default_architecture_summary(), _default_module_description(), _derive_complexity() (+40 more)

### Community 56 - "GuidelinesReader"
Cohesion: 0.07
Nodes (27): DocumentChunk, GuidelinesReader, GuidelinesStatus, callable, Path, Guidelines RAG - reads design-standard documents and injects relevant chunks…, Scan guidelines_dir, parse docs, embed chunks (or fallback), cache results.…, Retrieve top-N most relevant chunks and return a Markdown context block.… (+19 more)

### Community 57 - "ValidationReport"
Cohesion: 0.06
Nodes (27): _build_generation_summary(), _count_report_findings(), BaseModel, A single validation issue found during model checking., Complete validation report for a set of generated models., ValidationIssue, ValidationReport, ClassDiagram (+19 more)

### Community 58 - "ActivityPipeline"
Cohesion: 0.07
Nodes (27): ActivityPipeline, _extract_json(), Any, Fall-back: build skeleton entries from the parsed MUD context., Extract inferred values from the Stage 1 skeleton for user visibility. Surfaces…, Repair / drop edges whose source/target don't match any node id, then auto-fill…, Build IRV and DEM cross-reference dicts for the reviewer. Primary source: the…, Phase A of two-phase Stage 3 — generate topology (types + edges) only. Returns… (+19 more)

### Community 59 - "AUTOSAR MUD Skill — APPENDIX (Reference Only)"
Cohesion: 0.04
Nodes (46): A1.1 Software Component Types, A1.2 Port and Interface Summary, A1.3 Communication Paradigms, A1.4 Runnable Entities and RTE Events, A1.5 ExclusiveArea and InterRunnableVariable, §A1 — AUTOSAR Concepts Reference, §A2 — Naming Keyword Cheat Sheet (AUTOSAR Appendix A Subset), A3.1 Type Hierarchy (+38 more)

### Community 60 - "mud_activity_context.py"
Cohesion: 0.13
Nodes (30): _ActivityGraphBuilder, _classify_step_kind(), _compact_step_label(), _contains_structural_hint(), _count_helper_calls(), _expand_numbered_step_block(), _extract_helper_call(), _extract_helper_functions() (+22 more)

### Community 61 - "mud_spec_generator.py"
Cohesion: 0.10
Nodes (31): apply_patch_only_review_fixes(), build_fix_manifest(), build_unresolved_review(), compare_review_results(), _coverage_tokens(), deterministic_requirement_coverage(), _extract_section7(), format_fix_manifest() (+23 more)

### Community 62 - "mud_pipeline_stages.py"
Cohesion: 0.08
Nodes (27): JSON schemas for per-element MUD spec generation. Each schema is passed as the…, _assemble_markdown(), _extract_json(), _fmt_range_unit(), _focus_requirements(), _format_hints_block(), _load_reference(), MudSpecPipeline (+19 more)

### Community 63 - "MermaidExporter"
Cohesion: 0.07
Nodes (18): MermaidExporter, AnyDiagram, ClassDiagram, ComponentDiagram, Path, SequenceDiagram, StateMachineDiagram, Export JSON-UML diagrams to Mermaid.js text format. (+10 more)

### Community 64 - "TraceabilityStore"
Cohesion: 0.07
Nodes (14): Traceability store - requirement-to-model element mapping with provenance., Get all model elements traced to a requirement., Get all requirements traced to a model element., Generate a traceability coverage report. Returns: Dict with coverage statistics…, Generate a full traceability matrix. Returns list of dicts with requirement_id,…, Mark a model element as accepted by human reviewer. Returns number of trace…, SQLite-backed store for requirement-to-model traceability. Provides: -…, Create the database and tables if they don't exist. Failures are caught and… (+6 more)

### Community 65 - "STEP 5 — MERMAID GENERATION ALGORITHM"
Cohesion: 0.06
Nodes (31): APPENDIX REFERENCE GUIDE, AUTOSAR MUD Skill — CORE (Active Execution Instructions), Default Assumption Table (use when Key Fact is absent, flag with [ASSUMPTION]), EXECUTION ORDER — FOLLOW THIS SEQUENCE EVERY TIME, PAT_CS_CLIENT — Runnable Calling a Client-Server Operation, PAT_CYCLIC_SR — Cyclic, Single Rate, Sender-Receiver, PAT_EVENT_DRIVEN — DataReceivedEvent Triggered Runnable, PAT_FILTER — Cyclic with Moving Average Filter (+23 more)

### Community 67 - "CloudBackend"
Cohesion: 0.12
Nodes (12): CloudBackend, Pull a missing Ollama model via 'ollama pull <model>'. Only attempted for local…, Generate using Anthropic Claude API., Cloud AI inference backend. Supports: - Anthropic Claude API (primary,…, Generate using OpenAI-compatible API., Stream generation token-by-token. Uses native SSE streaming for both Anthropic…, Stream from Anthropic API., Stream token-by-token from an OpenAI-compatible endpoint (Ollama, vLLM, etc.).… (+4 more)

### Community 68 - "TestParseResponseWrapper"
Cohesion: 0.13
Nodes (15): Verify orchestrator._parse_response handles all three JSON formats., Build a minimal AIOrchestrator without real AI backends., {"diagrams":[...], "analyzed_requirements":[...]} must unwrap correctly., Wrapper with 2 diagrams -> 2 ActivityDiagram objects in result., Flat {"diagram_type": "sequence", ...} format must still parse correctly., Before the fix, wrapper was parsed as ActivityDiagram -> nodes=[], edges=[]., Legacy payloads with node `type` and edges without `id` must parse., Legacy nodes without `name` must be auto-filled from description/id. (+7 more)

### Community 69 - "ImportResult"
Cohesion: 0.16
Nodes (18): BaseImporter, ImportResult, ABC, BaseModel, Base importer interface and common utilities., Result of an import operation., Abstract base class for requirement importers., CSV requirement importer. (+10 more)

### Community 70 - ".map_diagram"
Cohesion: 0.09
Nodes (16): AnyDiagram, ClassDiagram, ComponentDiagram, SequenceDiagram, StateMachineDiagram, Map state machine elements to AUTOSAR mode management., Map class diagram elements to AUTOSAR SWCs., Map component diagram elements to AUTOSAR architecture. (+8 more)

### Community 71 - "$defs"
Cohesion: 0.09
Nodes (24): required, type, required, type, $defs, ClassDiagram, ComponentDiagram, SequenceDiagram (+16 more)

### Community 72 - "_uid"
Cohesion: 0.13
Nodes (17): AnyDiagram, ClassDiagram, ComponentDiagram, Element, Path, SequenceDiagram, StateMachineDiagram, Export sequence diagram as UML Interaction. (+9 more)

### Community 73 - "MudSpecPipeline"
Cohesion: 0.13
Nodes (17): MudSpecPipeline, Two-stage MUD spec generator with per-runnable Section 7 expansion.      Produce, Args:             backend:           Default backend for all stages (Stage 3 alw, Parse JSON review result from AI response.          Tries multiple extraction st, Return a safe minimal review so the pipeline can still regenerate., Generate concrete suggestions from issues when the AI omitted the field., Override the AI's self-reported `approved` flag with our deterministic rule., Return a safe minimal review so the pipeline can still regenerate. (+9 more)

### Community 74 - "properties"
Cohesion: 0.08
Nodes (24): Message, type, type, default, type, default, type, type (+16 more)

### Community 75 - "properties"
Cohesion: 0.09
Nodes (23): type, enum, type, Provenance, type, type, type, ai_model (+15 more)

### Community 76 - "properties"
Cohesion: 0.10
Nodes (23): type, type, $ref, items, type, items, type, type (+15 more)

### Community 77 - "MudActivityContext"
Cohesion: 0.13
Nodes (15): MudActivityContext, RunnableContext, _FakeBackend, _make_requirement(), asyncio, test_stage3_runnable_backend_failure_returns_cfg_fallback(), test_stage3_runnable_rebuilds_invalid_ai_topology_from_cfg(), _make_ctx() (+7 more)

### Community 78 - "MUD Tool — AI-Assisted AUTOSAR Module & Unit Design"
Cohesion: 0.09
Nodes (22): AI Architecture, AUTOSAR Conventions, AUTOSAR Design Patterns Supported, Configuration Reference, Enhanced Workflow — 5 Stages, Export Formats, License, MUD Tool — AI-Assisted AUTOSAR Module & Unit Design (+14 more)

### Community 79 - "build_mud_activity_context"
Cohesion: 0.18
Nodes (21): build_mud_activity_context(), _extract_helper_functions(), _extract_subsections(), _extract_swc_name(), _parse_markdown_table(), synthesize_activity_diagrams_from_context(), _trim_markdown(), _generate_activity_from_mud() (+13 more)

### Community 80 - "section7_normalizer.py"
Cohesion: 0.18
Nodes (17): _canonicalize_calls(), _collapse_blank_lines(), _dedupe_preserve_order(), _describe_ambiguous_line(), _format_code_like_text(), _leading_indent_units(), _looks_code_like(), _looks_code_sequence() (+9 more)

### Community 81 - "main.py"
Cohesion: 0.12
Nodes (19): FastAPI, Clean shutdown of all services., shutdown_services(), _find_env_file(), Locate the .env file relative to this settings module, regardless of CWD. The…, MUD Tool - AI-Assisted AUTOSAR Module & Unit Design Tool., lifespan(), main() (+11 more)

### Community 82 - ".export_diagram"
Cohesion: 0.17
Nodes (13): AnyDiagram, ClassDiagram, ComponentDiagram, Element, Path, SequenceDiagram, StateMachineDiagram, Export all diagrams, one .drawio file per diagram. Returns list of written file… (+5 more)

### Community 83 - "TestLiveExportEndpoints"
Cohesion: 0.11
Nodes (13): live, eps_generation_result(), fixture, MUD Tool — Activity Diagram Pipeline Tests…, POST /export/mermaid/inline must return ≥1 diagram with flowchart text., POST /export format=mermaid must write non-empty .mmd file., POST /export format=drawio must write non-empty .drawio file., Full generate test — requires Ollama + qwen2.5-coder:7b. (+5 more)

### Community 84 - "Message"
Cohesion: 0.11
Nodes (9): Lifeline, Message, A lifeline in a sequence diagram - maps to an AUTOSAR SWC/Runnable., A message in a sequence diagram - maps to an AUTOSAR RTE call., fixture, Tests for the AUTOSAR mapper., TestAUTOSARMapper, Invalid RTE call type should produce an error. (+1 more)

### Community 85 - "str"
Cohesion: 0.19
Nodes (7): _uid(), AssociationType, Visibility, str, test_graph_central_modules_are_classified_in_test_manifest(), test_python_sources_and_tests_parse_cleanly(), _top_graph_source_files()

### Community 86 - "properties"
Cohesion: 0.11
Nodes (20): type, properties, type, properties, type, type, type, const (+12 more)

### Community 87 - "RequirementBrowser"
Cohesion: 0.18
Nodes (7): DiagramGenerator, ImportResult, RequirementBrowser, RequirementRecord, ImportResult, MUDToolWorkflow, WorkflowResult

### Community 88 - "build_mud_activity_context"
Cohesion: 0.21
Nodes (18): build_mud_activity_context(), _parse_numbered_step_entries(), _parse_numbered_steps(), Build deterministic activity diagrams from Section 7 numbered steps. This is…, synthesize_activity_diagrams_from_context(), test_build_mud_activity_context_extracts_runnables_and_flow(), test_build_mud_activity_context_handles_numbered_subheadings(), test_parse_numbered_step_entries_expands_c_style_pseudocode_blocks() (+10 more)

### Community 89 - "Section7NormalizationResult"
Cohesion: 0.12
Nodes (10): Normalise Section 7 + detect prose. When ``auto_repair_context`` is a dict,…, detect_pure_prose_steps(), _extract_runnable_sections(), normalize_section7_markdown(), Scan Section 7 markdown for steps whose code body is pure English prose.…, Section7NormalizationResult, test_normalize_section7_preserves_ambiguous_prose_with_warning(), test_normalize_section7_rewrites_header_plus_helper_and_assignment_sequence() (+2 more)

### Community 90 - "TestGuidelineConstants"
Cohesion: 0.10
Nodes (6): AUTOSAR Section 7 pseudo-code style guide — single source of truth. Every…, Tests for Phase PSEUDO: strict Section 7 pseudo-code enforcement. Covers: P-1:…, Verify Stage 3 imports _step_body_is_pure_prose for retry logic., TestGuidelineConstants, TestPromptSandwichPattern, TestStage3ProseRetry

### Community 91 - "diagnose_eps_flowchart_pipeline.py"
Cohesion: 0.27
Nodes (19): _activity_diagram_summary(), _canonical_activity_summary(), _default_csv(), _default_output_dir(), _looks_like_placeholder_summary(), main(), _make_markdown_report(), _now_stamp() (+11 more)

### Community 92 - "activity_pipeline_stages.py"
Cohesion: 0.21
Nodes (13): _diagram_has_cfg_breakage(), _ensure_helper_subdiagrams(), _extract_assumptions(), _extract_json(), _finalize_cfg_fallback(), _normalize_activity_semantics(), _overlay_ai_on_cfg(), _repair_decision_branches() (+5 more)

### Community 94 - "properties"
Cohesion: 0.11
Nodes (19): type, maximum, minimum, type, default, type, default, type (+11 more)

### Community 95 - "section7_normalizer.py"
Cohesion: 0.22
Nodes (17): _canonicalize_calls(), _collapse_blank_lines(), _dedupe_preserve_order(), _describe_ambiguous_line(), _format_code_like_text(), _leading_indent_units(), _looks_code_like(), _looks_code_sequence() (+9 more)

### Community 96 - "conftest.py"
Cohesion: 0.14
Nodes (18): ClassDiagram, fixture, SequenceDiagram, StateMachineDiagram, Shared test fixtures for the MUD Tool test suite., Create a sample sequence diagram for testing., Create a sample state machine diagram for testing., Create a sample class diagram for testing. (+10 more)

### Community 97 - "SidecarClient"
Cohesion: 0.17
Nodes (6): com.fasterxml.jackson.databind.ObjectMapper, MediaType, SidecarClient, MUDToolModule, OkHttpClient, org.slf4j.Logger

### Community 98 - "properties"
Cohesion: 0.11
Nodes (18): type, Transition, type, action, guard, source, target, trace_req (+10 more)

### Community 99 - "diagnose_eps_flowchart_pipeline.py"
Cohesion: 0.23
Nodes (17): _activity_diagram_summary(), _canonical_activity_summary(), _default_csv(), _default_output_dir(), _looks_like_placeholder_summary(), main(), _make_markdown_report(), _now_stamp() (+9 more)

### Community 100 - "properties"
Cohesion: 0.12
Nodes (17): type, type, properties, id, runnable, source_requirements, stereotype, trace_reqs (+9 more)

### Community 102 - "_ActivityGraphBuilder"
Cohesion: 0.38
Nodes (4): _ActivityGraphBuilder, _extract_rte_metadata(), _infer_element_name(), _short_step_description()

### Community 103 - ".export_diagram"
Cohesion: 0.12
Nodes (8): Export all ActivityDiagrams in a GenerationResult. Returns: {diagram_name:…, Recursively walk the node graph and emit C code. ``stop_at`` is the join node…, Put a yes/true branch first and a no/else branch last., C condition for the first branch. An expression guard (e.g. ``u16Volt > MAX``)…, Nearest node reachable from every branch — the if/else join point., Variables of the diagram and all its sub-diagrams, declared once at file scope., Scan node names for MISRA-C Hungarian variable patterns and return (type, name)…, Generate C skeleton code for a single ActivityDiagram. ``_nested`` is set for…

### Community 104 - ".export_diagram"
Cohesion: 0.12
Nodes (9): AnyDiagram, ClassDiagram, ComponentDiagram, Path, SequenceDiagram, StateMachineDiagram, Export an activity / code-flow diagram to PlantUML., Export all diagrams in a generation result to PlantUML files. Returns list of… (+1 more)

### Community 105 - "debug_trace.py"
Cohesion: 0.24
Nodes (9): _is_secret_key(), Any, Per-run structured debug trace for UI-triggered generation workflows., _safe_json_value(), _summarize_large_value(), _utc_now(), _read_jsonl(), test_run_debug_trace_recreates_latest_file_each_run() (+1 more)

### Community 108 - "MarkdownImporter"
Cohesion: 0.20
Nodes (7): MarkdownImporter, ImportResult, Path, Import requirements from Markdown table files., Parse a markdown table row into cell values., Check if a line is a markdown table separator (e.g., |---|---|)., TestMarkdownImporter

### Community 110 - "test_module_planner.py"
Cohesion: 0.20
Nodes (7): _FailingBackend, _FailingOrchestrator, _FakeBackend, _FakeOrchestrator, test_module_planner_falls_back_when_backend_connection_fails(), test_module_planner_recovers_from_empty_ai_output_using_requirement_evidence(), test_module_planner_repairs_partial_ai_module_with_requirement_evidence()

### Community 111 - "Current Implementation Architecture (Updated)"
Cohesion: 0.14
Nodes (14): 10. UI architecture, 11. Design philosophy of the current architecture, 1. System shape, 2. Main runtime layers, 3. API architecture, 5. Current MUD-first workflow architecture, 8. Export architecture, 9. Persistence and traceability architecture (+6 more)

### Community 112 - "mud_spec_generator.py"
Cohesion: 0.27
Nodes (10): apply_patch_only_review_fixes(), _coverage_tokens(), deterministic_requirement_coverage(), _extract_section7(), _guess_patch_runnable(), MUD Spec Generator — generates detailed Module Unit Design specification docs., Best-effort deterministic coverage signal for Section 7.      This is intentio, Patch only targeted Section 7 runnable blocks for coverage gaps.      Returns (+2 more)

### Community 113 - "review_issue_fingerprint"
Cohesion: 0.18
Nodes (12): build_fix_manifest(), build_unresolved_review(), compare_review_results(), Stable key for matching repeated review findings across iterations., Convert review output into required, actionable regeneration fixes., Return a SpecReviewResult containing ONLY the issues that were NOT fixed., review_fix_fingerprints(), review_issue_fingerprint() (+4 more)

### Community 114 - "TestBuildSignalTable"
Cohesion: 0.24
Nodes (3): Build a per-runnable available-signals table for Stage 3 injection. Combines…, End-to-end: _build_signal_table output must appear in formatted prompt., TestBuildSignalTable

### Community 115 - "test_c_skeleton_exporter.py"
Cohesion: 0.26
Nodes (11): C-code skeleton generator from ActivityDiagram JSON. Walks the node/edge graph…, _body_lines(), _diamond(), _node(), CSkeletonExporter: control-flow structure of the emitted C code., Start → Read → [Volt > Max?] → (yes: Fault | no: Normal) → Merge → Write → End, test_code_after_merge_is_emitted_once_after_if_else(), test_expression_guard_used_verbatim() (+3 more)

### Community 116 - ".render_all"
Cohesion: 0.19
Nodes (7): Path, Render all diagrams in a generation result to image files. Args: result:…, Render via Kroki.io REST API (POST method with JSON body)., Render diagram text via Kroki.io REST API (POST method with JSON body)., Render using a local plantuml.jar subprocess., Render PlantUML text to SVG bytes. Uses local plantuml.jar if configured,…, Render PlantUML text to PNG bytes.

### Community 117 - "._check_state_machine_owners"
Cohesion: 0.22
Nodes (8): ClassDiagram, ComponentDiagram, SequenceDiagram, StateMachineDiagram, Sequence diagram lifelines should correspond to components., State machine owners should correspond to known SWCs., Port definitions should be consistent across diagrams., Sequence diagram messages should match class diagram operations.

### Community 118 - "_FakeBackend"
Cohesion: 0.36
Nodes (5): _FakeBackend, _make_pipeline(), asyncio, Returns pre-canned JSON payloads in order., TestTwoPhaseStage3

### Community 119 - "._extract_text"
Cohesion: 0.17
Nodes (6): Parse document → list of (section_title, text) pairs., Extract sections from HTML by walking h1/h2/h3 heading tags., Extract sections from PDF using pypdf., Extract sections from DOCX using python-docx., Extract sections from Excel by treating each sheet as a section.          Each r, Extract sections from TXT/MD by Markdown headings or paragraph breaks.

### Community 120 - "Clean shutdown of all services."
Cohesion: 0.18
Nodes (11): Clean shutdown of all services., shutdown_services(), _find_env_file(), Locate the .env file relative to this settings module, regardless of CWD.      T, lifespan(), main(), MUD Tool Sidecar - FastAPI application entry point.  Runs as a localhost HTTP se, CLI entry point for the sidecar server. (+3 more)

### Community 121 - "enum"
Cohesion: 0.17
Nodes (12): rte_call, enum, type, Rte_Call, Rte_IRead, Rte_IWrite, Rte_Read, Rte_Receive (+4 more)

### Community 123 - "ValidationPanel"
Cohesion: 0.27
Nodes (3): ValidationIssueRecord, ValidationPanel, ValidationSummary

### Community 124 - "TestBuildIrvCoherenceBlock"
Cohesion: 0.32
Nodes (3): Build cross-runnable IRV coherence context for Stage 3 injection. Shows which…, End-to-end: IRV coherence block must appear in formatted prompt., TestBuildIrvCoherenceBlock

### Community 125 - "._parse_response"
Cohesion: 0.25
Nodes (8): _build_evidence_summary(), _default_architecture_summary(), _extract_json_payload(), PlanResult, Result returned by ModulePlanner.plan_modules()., Run AI module planning on the supplied requirements text.          Args:, Extract JSON from the AI response and build PlanResult., _sort_modules()

### Community 126 - "ReviewIssue"
Cohesion: 0.24
Nodes (7): _auto_suggestions(), _enforce_approval_rules(), _fallback_review(), from_dict(), Run an AI review pass on a generated MUD spec.          Args:             swc, Parse JSON review result from AI response.          Tries multiple extraction, ReviewIssue

### Community 127 - "PMSM_FOC_Architecture_Requirements_6d06e0b3.md"
Cohesion: 0.18
Nodes (10): Sheet: 00_Overview, Sheet: 01_SigFlow, Sheet: 02_SpdCtrl, Sheet: 03_CurrCtrl, Sheet: 04_MtrMon, Sheet: 05_AllPorts, Sheet: 06_AllRunnables, Sheet: 07_CalibParams (+2 more)

### Community 128 - "._parse_review"
Cohesion: 0.20
Nodes (5): Run an AI review pass on a generated MUD spec. Args: swc_name: SWC name for…, Override the AI's self-reported `approved` flag with our deterministic rule.…, Parse JSON review result from AI response. Tries multiple extraction strategies…, Return a safe minimal review so the pipeline can still regenerate., Generate concrete suggestions from issues when the AI omitted the field.

### Community 129 - ".import_file"
Cohesion: 0.25
Nodes (5): ImportResult, Path, Get the appropriate importer for a given file. Args: file_path: Path to the…, Convenience method: auto-detect format and import requirements. Args:…, TestImporterFactory

### Community 130 - "TextImporter"
Cohesion: 0.25
Nodes (5): ImportResult, Path, Import requirements from plain text files. Supports two formats: 1. Pipe-…, TextImporter, TestTextImporter

### Community 132 - "TraceabilityMatrix"
Cohesion: 0.38
Nodes (5): CoverageInfo, TraceabilityData, TraceabilityMatrix, TraceElement, TraceEntry

### Community 133 - "._build_requirement"
Cohesion: 0.20
Nodes (5): Parse requirement type string to enum., Parse ASIL level string to enum., Parse priority string to enum., Parse status string to enum., Build a Requirement from a mapped row dict. Args: row_data: Dict of canonical…

### Community 134 - "CSVImporter"
Cohesion: 0.27
Nodes (5): CSVImporter, ImportResult, Path, Import requirements from CSV files. Same column structure as Excel template but…, TestCSVImporter

### Community 136 - "csv_to_reference_json.py"
Cohesion: 0.36
Nodes (9): convert(), _format_calib_example(), _format_port_example(), _format_runnable_example(), main(), print_summary(), Path, Convert EPS_MUD_Enhanced.csv (19-column tabular MUD spec) to a structured JSON… (+1 more)

### Community 137 - "drawio_exporter.py"
Cohesion: 0.33
Nodes (5): _activity_node_label(), _activity_node_style(), _boxes_overlap(), _branch_sort_key(), _estimate_activity_node_size()

### Community 139 - "_safe_json_value"
Cohesion: 0.36
Nodes (5): _is_secret_key(), Per-run structured debug trace for UI-triggered generation workflows., _safe_json_value(), _summarize_large_value(), _utc_now()

### Community 141 - "normalize_section7_markdown"
Cohesion: 0.36
Nodes (7): _extract_runnable_sections(), normalize_section7_markdown(), _estimate_planned_diagrams(), test_normalize_section7_preserves_ambiguous_prose_with_warning(), test_normalize_section7_rewrites_header_plus_helper_and_assignment_sequence(), test_normalize_section7_rewrites_inline_control_flow_and_calls(), test_normalized_section7_improves_activity_context_branching()

### Community 142 - "Lifeline"
Cohesion: 0.29
Nodes (8): Lifeline, State, required, type, required, type, id, name

### Community 144 - "ExcelImporter"
Cohesion: 0.29
Nodes (5): ExcelImporter, ImportResult, Path, Import requirements from Excel (.xlsx) files. Supports: - Polarion ALM Excel…, Import requirements from an Excel file. The importer: 1. Opens the workbook…

### Community 145 - "_EmptyReviewBackend"
Cohesion: 0.32
Nodes (5): _EmptyReviewBackend, _ReviewOrchestrator, test_deterministic_coverage_detects_explicit_section7_trace(), test_empty_ai_review_response_is_info_when_deterministic_coverage_passes(), test_patch_only_review_fixes_target_section7_without_rewriting_other_sections()

### Community 146 - "Troubleshooting"
Cohesion: 0.25
Nodes (8): Generation returns empty diagrams, `ModuleNotFoundError: No module named 'mudtool'`, MUD Spec generates but is very short, Plan Modules returns no results, Port 8042 already in use, Server starts but Web UI shows "AI: offline", SVG export fails, Troubleshooting

### Community 147 - ".regenerate_spec"
Cohesion: 0.29
Nodes (5): format_fix_manifest(), Regenerate an improved MUD spec by fixing all issues from the review report., Remove accidental model-emitted fix coverage notes from user-visible spec., strip_fix_coverage_block(), test_strip_fix_coverage_block_removes_internal_notes()

### Community 148 - "Design Guidelines Folder"
Cohesion: 0.29
Nodes (6): Clearing the Cache, Configuration (`.env`), Design Guidelines Folder, How It Works, Supported Formats, Vector Embeddings (recommended)

### Community 150 - "TestAutoRepairGate"
Cohesion: 0.29
Nodes (3): Loop guard: if context.repaired is True, do NOT signal another repair., When auto_repair_context dict is supplied and prose is found, the context is…, TestAutoRepairGate

### Community 152 - "._repair_section7_prose"
Cohesion: 0.33
Nodes (3): Normalise Section 7 and trigger ONE-SHOT prose repair if needed. Used by…, Targeted one-shot regeneration when Section 7 contains pure-prose steps. Builds…, Generate the MUD spec Markdown for the selected SWC. Args: swc_name: AUTOSAR…

### Community 153 - "ValidationSeverity"
Cohesion: 0.40
Nodes (5): Enum, str, Validation result models., Validation issue severity levels., ValidationSeverity

### Community 154 - "_EmptyReviewBackend"
Cohesion: 0.33
Nodes (4): _EmptyReviewBackend, asyncio, _ReviewOrchestrator, test_empty_ai_review_response_is_info_when_deterministic_coverage_passes()

### Community 155 - "4. AI subsystem architecture"
Cohesion: 0.33
Nodes (6): 4. AI subsystem architecture, Activity / flowchart generation, Core orchestrator and pipelines, MUD-spec generation, Prompt, guidelines, and backend adapters, Requirement and module understanding

### Community 156 - ".import_file"
Cohesion: 0.40
Nodes (3): Path, Import requirements from a file. Args: file_path: Path to the input file.…, Check if this importer supports the given file format.

### Community 157 - "MUD Tool Test Strategy"
Cohesion: 0.40
Nodes (4): Current Known Gaps, Graph-Informed Coverage, MUD Tool Test Strategy, Standard Commands

### Community 159 - "6. Activity / flowchart architecture"
Cohesion: 0.50
Nodes (4): 6. Activity / flowchart architecture, Current activity path, What the activity architecture now combines, Why activity generation is separate

### Community 160 - "REST API"
Cohesion: 0.50
Nodes (4): Core Pipeline, Enhanced Workflow — Module Planning & MUD Spec *(new)*, Export & Traceability, REST API

### Community 161 - "Requirement File Formats"
Cohesion: 0.50
Nodes (4): CSV (recommended), Markdown table, Pipe-delimited text, Requirement File Formats

### Community 162 - "Installation"
Cohesion: 0.50
Nodes (4): Installation, Step 1 — Run setup, Step 2 — Configure AI backend, Step 3 — Start the server

### Community 165 - "7. Data model and validation architecture"
Cohesion: 0.67
Nodes (3): 7. Data model and validation architecture, Canonical internal model, Validation stack

### Community 166 - "Hardware Requirements"
Cohesion: 0.67
Nodes (3): Hardware Requirements, With Anthropic Claude API (cloud), With Ollama (recommended — local, free, no API key)

## Knowledge Gaps
- **241 isolated node(s):** `$schema`, `title`, `description`, `oneOf`, `type` (+236 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **52 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `json_uml.py` to `ActivityDiagram`, `Message`, `RequirementSet`, `.import_file`, `GenerationResult`, `TraceabilityStore`, `PlantUMLExporter`, `routes.py`, `Settings`, `Message`, `GenerationResult`, `Settings`, `StructuralValidator`?**
  _High betweenness centrality (0.329) - this node is a cross-community bridge._
- **Why does `GenerationResult` connect `GenerationResult` to `_ActivityLayoutBox`, `routes.py`, `ActivityDiagram`, `json_uml.py`, `models/__init__.py`, `AIOrchestrator`, `ValidationReport`, `MermaidExporter`, `TraceabilityStore`, `TestParseResponseWrapper`, `.map_diagram`, `_uid`, `.export_diagram`, `TestLiveExportEndpoints`, `Message`, `conftest.py`, `.export_diagram`, `.export_diagram`, `test_c_skeleton_exporter.py`, `.render_all`, `._check_state_machine_owners`?**
  _High betweenness centrality (0.150) - this node is a cross-community bridge._
- **Why does `Settings` connect `Settings` to `TraceabilityStore`, `GenerationResult`, `conftest.py`, `CloudBackend`, `TestParseResponseWrapper`, `routes.py`, `Requirement`, `json_uml.py`, `TestLiveExportEndpoints`, `models/__init__.py`, `AIOrchestrator`, `Message`, `ActivityDiagram`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **Are the 447 inferred relationships involving `Settings` (e.g. with `ChunkedElaborator` and `Chunked Requirement Elaboration for Small Models (2–3B parameters).  Instead of`) actually correct?**
  _`Settings` has 447 INFERRED edges - model-reasoned connections that need verification._
- **Are the 442 inferred relationships involving `GenerationResult` (e.g. with `AIOrchestrator` and `.generate_all_diagrams()`) actually correct?**
  _`GenerationResult` has 442 INFERRED edges - model-reasoned connections that need verification._
- **Are the 348 inferred relationships involving `ActivityDiagram` (e.g. with `ActivityPipeline` and `Multi-stage activity-diagram generation pipeline.  Mirrors the design of ``mud_p`) actually correct?**
  _`ActivityDiagram` has 348 INFERRED edges - model-reasoned connections that need verification._
- **Are the 322 inferred relationships involving `DiagramType` (e.g. with `ActivityPipeline` and `Multi-stage activity-diagram generation pipeline.  Mirrors the design of ``mud_p`) actually correct?**
  _`DiagramType` has 322 INFERRED edges - model-reasoned connections that need verification._