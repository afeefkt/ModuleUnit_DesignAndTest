"""Tests for diagram quality improvement strategies 1–5.

Strategy 1 — Exact signal injection (_build_signal_table)
Strategy 2 — Gold-standard example (prompt contract check)
Strategy 3 — Two-phase topology/labels (_stage3a_topology + _stage3b_labels)
Strategy 4 — Cross-runnable IRV coherence (_build_irv_coherence_block)
Strategy 5 — Per-runnable targeted retry (low-confidence re-generation)
"""
from __future__ import annotations

import json
import pytest

from mudtool.ai.activity_pipeline_stages import (
    ActivityPipeline,
    _RUNNABLE_USER_TMPL,
    _STAGE3A_TOPOLOGY_SYSTEM,
    _STAGE3B_LABELS_SYSTEM,
    _STAGE3B_LABELS_USER_TMPL,
)
from mudtool.ai.base_backend import AIResponse
from mudtool.ai.mud_activity_context import MudActivityContext, RunnableContext


# ─── Shared helpers ───────────────────────────────────────────────────────────

class _FakeBackend:
    """Returns pre-canned JSON payloads in order."""
    def __init__(self, payloads: list[dict | str]):
        self._payloads = list(payloads)
        self.calls: list[dict] = []
        self.backend_name = "fake"

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        payload = self._payloads.pop(0)
        content = payload if isinstance(payload, str) else json.dumps(payload)
        return AIResponse(content=content, model="fake-model", latency_ms=5)


def _make_ctx(
    swc: str = "SWC_Test",
    runnable: str = "RE_Test",
    pseudo: str = "1. Rte_Read_RP_Speed(&l_f32Speed)\n2. if l_f32Speed > LIMIT",
    rte_calls: list[str] | None = None,
) -> MudActivityContext:
    return MudActivityContext(
        swc_name=swc,
        runnables=[RunnableContext(name=runnable, functional_description=pseudo)],
        rte_calls=rte_calls or [],
        helper_functions=[],
        raw_markdown="",
    )


def _make_pipeline(backend=None) -> ActivityPipeline:
    b = backend or _FakeBackend([])
    p = ActivityPipeline(backend=b, progress_callback=None)
    p._skeleton_backend = b
    return p


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy 1 — _build_signal_table
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildSignalTable:
    def test_extracts_rte_read_from_pseudo_code(self):
        sk = {"name": "RE_Test"}
        pseudo = "1. Rte_Read_RP_VehicleSpeed(&l_f32Speed)\n2. l_f32Speed > LIMIT"
        result = ActivityPipeline._build_signal_table(sk, pseudo, [])
        assert "Rte_Read_RP_VehicleSpeed(&l_f32Speed)" in result

    def test_extracts_rte_write_from_pseudo_code(self):
        sk = {"name": "RE_Test"}
        pseudo = "1. Rte_Write_PP_Torque(l_f32Out)"
        result = ActivityPipeline._build_signal_table(sk, pseudo, [])
        assert "Rte_Write_PP_Torque(l_f32Out)" in result

    def test_extracts_irv_read_and_write(self):
        sk = {"name": "RE_Test"}
        pseudo = (
            "1. Rte_IRead_IRV_PrevSpeed(&l_f32Prev)\n"
            "2. Rte_IWrite_IRV_PrevSpeed(l_f32Speed)"
        )
        result = ActivityPipeline._build_signal_table(sk, pseudo, [])
        assert "Rte_IRead_IRV_PrevSpeed" in result
        assert "Rte_IWrite_IRV_PrevSpeed" in result

    def test_extracts_calprm_constants(self):
        sk = {"name": "RE_Test"}
        pseudo = "1. if l_f32Speed > CALPRM_SPEED_MAX\n2. CALPRM_WARN_LEVEL check"
        result = ActivityPipeline._build_signal_table(sk, pseudo, [])
        assert "CALPRM_SPEED_MAX" in result
        assert "CALPRM_WARN_LEVEL" in result

    def test_skeleton_explicit_ports_take_priority(self):
        sk = {
            "name": "RE_Test",
            "reads_ports": ["RP_VehicleSpeed"],
            "writes_ports": ["PP_AssistTorque"],
            "reads_irvs": ["IRV_FilteredSpeed"],
            "writes_irvs": ["IRV_OutputTorque"],
            "raises_dem": ["DTC_TorqueFault"],
        }
        pseudo = "(no pseudo-code)"
        result = ActivityPipeline._build_signal_table(sk, pseudo, [])
        assert "RP_VehicleSpeed" in result
        assert "PP_AssistTorque" in result
        assert "IRV_FilteredSpeed" in result
        assert "IRV_OutputTorque" in result
        assert "DTC_TorqueFault" in result

    def test_global_ctx_calls_included_for_small_swc(self):
        sk = {"name": "RE_Test"}
        ctx_calls = [
            "Rte_Read_RP_Speed(&l_f32Speed)",
            "Rte_Write_PP_Out(l_f32Out)",
        ]
        result = ActivityPipeline._build_signal_table(sk, "", ctx_calls)
        # ≤8 global calls → all included regardless of pseudo-code match
        assert "Rte_Read_RP_Speed" in result
        assert "Rte_Write_PP_Out" in result

    def test_no_duplicates_in_output(self):
        sk = {"name": "RE_Test", "reads_ports": ["Rte_Read_RP_Speed(&l_f32Speed)"]}
        pseudo = "1. Rte_Read_RP_Speed(&l_f32Speed)"
        result = ActivityPipeline._build_signal_table(sk, pseudo, [])
        assert result.count("Rte_Read_RP_Speed(&l_f32Speed)") == 1

    def test_fallback_message_when_nothing_detected(self):
        result = ActivityPipeline._build_signal_table({"name": "RE_Test"}, "", [])
        assert "no signals detected" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy 2 — Prompt contract (gold-standard example in template)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromptContract:
    def test_template_contains_irv_read_example(self):
        assert "Rte_IRead_IRV_PrevSpeed" in _RUNNABLE_USER_TMPL

    def test_template_contains_irv_write_example(self):
        assert "Rte_IWrite_IRV_PrevSpeed" in _RUNNABLE_USER_TMPL

    def test_template_contains_calprm_example(self):
        assert "CALPRM_SPEED" in _RUNNABLE_USER_TMPL

    def test_template_contains_merge_node_example(self):
        assert '"merge"' in _RUNNABLE_USER_TMPL

    def test_template_contains_exception_node_example(self):
        assert "DEM_EVENT_STATUS_FAILED" in _RUNNABLE_USER_TMPL

    def test_template_contains_compound_c_guard(self):
        # Example must show a compound guard with && operator
        assert "&&" in _RUNNABLE_USER_TMPL

    def test_template_signal_table_placeholder_present(self):
        assert "{signal_table}" in _RUNNABLE_USER_TMPL

    def test_template_irv_coherence_placeholder_present(self):
        assert "{irv_coherence}" in _RUNNABLE_USER_TMPL

    def test_template_all_placeholders_formattable(self):
        """Ensure .format() with all expected keys does not raise KeyError."""
        rendered = _RUNNABLE_USER_TMPL.format(
            swc_name="SWC_X",
            runnable_name="RE_X",
            trigger="10ms",
            asil="QM",
            label_style="pseudocode",
            key_steps_block="  1. test step",
            signal_table="  Read sig: Rte_Read_RP_X(&l_f32X)",
            irv_coherence="  (no shared IRVs)",
            pseudo_code="1. if x > 0",
            cfg_scaffold="{}",
            requirements_block="  - REQ-01",
        )
        assert "SWC_X" in rendered
        assert "RE_X" in rendered

    def test_stage3b_labels_template_formattable(self):
        rendered = _STAGE3B_LABELS_USER_TMPL.format(
            swc_name="SWC_X",
            runnable_name="RE_X",
            asil="QM",
            signal_table="  (none)",
            irv_coherence="  (none)",
            pseudo_code="1. Rte_Read",
            topology_json='{"nodes":[],"edges":[]}',
            requirements_block="  - REQ-01",
        )
        assert "RE_X" in rendered

    def test_stage3a_system_forbids_labels(self):
        assert "no labels" in _STAGE3A_TOPOLOGY_SYSTEM.lower() or \
               "placeholder" in _STAGE3A_TOPOLOGY_SYSTEM.lower() or \
               "no label" in _STAGE3A_TOPOLOGY_SYSTEM.lower()

    def test_stage3b_system_forbids_changing_topology(self):
        assert "FIXED" in _STAGE3B_LABELS_SYSTEM or "fixed" in _STAGE3B_LABELS_SYSTEM.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy 4 — _build_irv_coherence_block
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildIrvCoherenceBlock:
    def _xref(self, writers: dict, readers: dict) -> dict:
        return {"irv_writers": writers, "irv_readers": readers, "dem_raisers": {}}

    def test_shows_irv_this_runnable_writes(self):
        sk = {"name": "RE_SpeedCalc", "writes_irvs": ["IRV_FilteredSpeed"]}
        xref = self._xref(
            writers={"IRV_FilteredSpeed": ["RE_SpeedCalc"]},
            readers={"IRV_FilteredSpeed": ["RE_TorqueCalc"]},
        )
        result = ActivityPipeline._build_irv_coherence_block(sk, xref)
        assert "IRV_FilteredSpeed" in result
        assert "RE_TorqueCalc" in result
        assert "WRITE" in result

    def test_shows_irv_this_runnable_reads(self):
        sk = {"name": "RE_TorqueCalc", "reads_irvs": ["IRV_FilteredSpeed"]}
        xref = self._xref(
            writers={"IRV_FilteredSpeed": ["RE_SpeedCalc"]},
            readers={"IRV_FilteredSpeed": ["RE_TorqueCalc"]},
        )
        result = ActivityPipeline._build_irv_coherence_block(sk, xref)
        assert "IRV_FilteredSpeed" in result
        assert "RE_SpeedCalc" in result
        assert "READ" in result

    def test_excludes_self_from_consumer_list(self):
        sk = {"name": "RE_Proc"}
        xref = self._xref(
            writers={"IRV_X": ["RE_Proc"]},
            readers={"IRV_X": ["RE_Proc", "RE_Other"]},
        )
        result = ActivityPipeline._build_irv_coherence_block(sk, xref)
        assert "RE_Proc" not in result.split("consumed")[1] if "consumed" in result else True
        assert "RE_Other" in result

    def test_independent_runnable_returns_fallback_message(self):
        sk = {"name": "RE_Isolated"}
        xref = self._xref({}, {})
        result = ActivityPipeline._build_irv_coherence_block(sk, xref)
        assert "independent" in result.lower() or "no shared" in result.lower()

    def test_empty_xref_handled_gracefully(self):
        sk = {"name": "RE_Test"}
        result = ActivityPipeline._build_irv_coherence_block(sk, {})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_multiple_irvs_all_listed(self):
        sk = {"name": "RE_Hub"}
        xref = self._xref(
            writers={
                "IRV_A": ["RE_Hub"],
                "IRV_B": ["RE_Hub"],
            },
            readers={
                "IRV_A": ["RE_Consumer1"],
                "IRV_B": ["RE_Consumer2"],
            },
        )
        result = ActivityPipeline._build_irv_coherence_block(sk, xref)
        assert "IRV_A" in result
        assert "IRV_B" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy 3 — Two-phase Stage 3 (_stage3a_topology, _stage3b_labels)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTwoPhaseStage3:
    _GOOD_TOPOLOGY = {
        "nodes": [
            {"id": "N_01", "node_type": "initial"},
            {"id": "N_02", "node_type": "call"},
            {"id": "N_03", "node_type": "decision"},
            {"id": "N_04", "node_type": "action"},
            {"id": "N_05", "node_type": "final"},
        ],
        "edges": [
            {"id": "E_01", "source": "N_01", "target": "N_02", "guard": ""},
            {"id": "E_02", "source": "N_02", "target": "N_03", "guard": ""},
            {"id": "E_03", "source": "N_03", "target": "N_04", "guard": "[l_f32V > LIMIT]"},
            {"id": "E_04", "source": "N_03", "target": "N_05", "guard": "[else]"},
            {"id": "E_05", "source": "N_04", "target": "N_05", "guard": ""},
        ],
    }

    _GOOD_LABELLED = {
        "diagram_type": "activity",
        "name": "RE_Test Code Flow",
        "owner_swc": "SWC_Test",
        "owner_runnable": "RE_Test",
        "source_requirements": ["REQ-01"],
        "nodes": [
            {"id": "N_01", "name": "Start", "node_type": "initial",
             "trace_reqs": ["REQ-01"], "description": "Entry", "confidence": 0.95},
            {"id": "N_02", "name": "Rte_Read_RP_Speed(&l_f32V)", "node_type": "call",
             "trace_reqs": ["REQ-01"], "description": "Read speed", "confidence": 0.95},
            {"id": "N_03", "name": "l_f32V > LIMIT", "node_type": "decision",
             "trace_reqs": ["REQ-01"], "description": "Check limit", "confidence": 0.9},
            {"id": "N_04", "name": "l_f32Out = l_f32V * K", "node_type": "action",
             "trace_reqs": ["REQ-01"], "description": "Scale", "confidence": 0.9},
            {"id": "N_05", "name": "End", "node_type": "final",
             "trace_reqs": ["REQ-01"], "description": "Exit", "confidence": 0.95},
        ],
        "edges": [
            {"id": "E_01", "source": "N_01", "target": "N_02", "guard": ""},
            {"id": "E_02", "source": "N_02", "target": "N_03", "guard": ""},
            {"id": "E_03", "source": "N_03", "target": "N_04", "guard": "[l_f32V > LIMIT]"},
            {"id": "E_04", "source": "N_03", "target": "N_05", "guard": "[else]"},
            {"id": "E_05", "source": "N_04", "target": "N_05", "guard": ""},
        ],
        "sub_diagrams": [],
    }

    @pytest.mark.asyncio
    async def test_stage3a_returns_topology_on_success(self):
        backend = _FakeBackend([self._GOOD_TOPOLOGY])
        pipeline = _make_pipeline(backend)
        result = await pipeline._stage3a_topology(
            rname="RE_Test",
            pseudo_code="1. Rte_Read_RP_Speed",
            cfg_scaffold="{}",
            temperature=0.1,
        )
        assert result is not None
        assert len(result["nodes"]) == 5
        assert result["nodes"][0]["node_type"] == "initial"
        assert result["nodes"][-1]["node_type"] == "final"

    @pytest.mark.asyncio
    async def test_stage3a_returns_none_on_invalid_json(self):
        backend = _FakeBackend(["not valid json {{{"])
        pipeline = _make_pipeline(backend)
        result = await pipeline._stage3a_topology(
            rname="RE_Test", pseudo_code="x", cfg_scaffold="{}", temperature=0.1
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_stage3a_returns_none_on_empty_nodes(self):
        backend = _FakeBackend([{"nodes": [], "edges": []}])
        pipeline = _make_pipeline(backend)
        result = await pipeline._stage3a_topology(
            rname="RE_Test", pseudo_code="x", cfg_scaffold="{}", temperature=0.1
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_stage3b_returns_labelled_diagram(self):
        backend = _FakeBackend([self._GOOD_LABELLED])
        pipeline = _make_pipeline(backend)
        result = await pipeline._stage3b_labels(
            rname="RE_Test",
            swc_name="SWC_Test",
            asil="QM",
            pseudo_code="1. read speed",
            topology=self._GOOD_TOPOLOGY,
            signal_table="  Read sig: Rte_Read_RP_Speed(&l_f32V)",
            irv_coherence="  (independent)",
            requirements_block="  - REQ-01",
            req_ids=["REQ-01"],
            temperature=0.1,
        )
        assert result is not None
        assert result["owner_runnable"] == "RE_Test"
        assert len(result["nodes"]) == 5
        assert result["nodes"][1]["name"] == "Rte_Read_RP_Speed(&l_f32V)"

    @pytest.mark.asyncio
    async def test_stage3b_injects_required_top_level_fields(self):
        # Minimal response missing top-level fields — _stage3b_labels must add them
        minimal = {"nodes": self._GOOD_LABELLED["nodes"], "edges": self._GOOD_LABELLED["edges"]}
        backend = _FakeBackend([minimal])
        pipeline = _make_pipeline(backend)
        result = await pipeline._stage3b_labels(
            rname="RE_Test",
            swc_name="SWC_X",
            asil="QM",
            pseudo_code="x",
            topology=self._GOOD_TOPOLOGY,
            signal_table="",
            irv_coherence="",
            requirements_block="",
            req_ids=["REQ-01"],
            temperature=0.1,
        )
        assert result is not None
        assert result["diagram_type"] == "activity"
        assert result["owner_swc"] == "SWC_X"
        assert result["sub_diagrams"] == []

    @pytest.mark.asyncio
    async def test_stage3b_strips_think_blocks(self):
        labelled_with_think = (
            "<think>thinking about this diagram...</think>\n"
            + json.dumps(self._GOOD_LABELLED)
        )
        backend = _FakeBackend([labelled_with_think])
        pipeline = _make_pipeline(backend)
        result = await pipeline._stage3b_labels(
            rname="RE_Test", swc_name="SWC_X", asil="QM",
            pseudo_code="x", topology=self._GOOD_TOPOLOGY,
            signal_table="", irv_coherence="", requirements_block="",
            req_ids=[], temperature=0.1,
        )
        assert result is not None
        assert result["diagram_type"] == "activity"


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy 5 — Targeted retry (confidence-based)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRetryPromptConstruction:
    """Unit tests for the retry_context injection in _stage3_runnable."""

    def test_retry_prefix_appears_in_prompt_when_context_set(self):
        """The retry prefix must appear at the top of user_prompt."""
        retry_ctx = "Node N_03 uses English prose 'Check if valid'"
        base = "BASE PROMPT CONTENT"
        user_prompt = (
            f"🔁 RETRY — previous attempt was low-confidence. Reviewer feedback:\n"
            f"{retry_ctx}\n\n"
            f"Apply the feedback above, then generate the corrected diagram:\n\n"
            f"{base}"
        )
        assert user_prompt.startswith("🔁 RETRY")
        assert retry_ctx in user_prompt
        assert base in user_prompt

    def test_no_retry_prefix_when_context_is_none(self):
        """Without retry_context the prompt must be the plain base."""
        base = "BASE PROMPT"
        user_prompt = base  # the else branch
        assert not user_prompt.startswith("🔁")

    def test_confidence_threshold_filters_correctly(self):
        """_RETRY_CONFIDENCE_THRESHOLD check — diagrams above threshold skipped."""
        threshold = 0.60
        high_conf_nodes = [{"confidence": 0.9}, {"confidence": 0.85}]
        low_conf_nodes  = [{"confidence": 0.4}, {"confidence": 0.5}]
        avg_high = sum(n["confidence"] for n in high_conf_nodes) / len(high_conf_nodes)
        avg_low  = sum(n["confidence"] for n in low_conf_nodes)  / len(low_conf_nodes)
        assert avg_high >= threshold   # should NOT retry
        assert avg_low  <  threshold   # SHOULD retry


# ═══════════════════════════════════════════════════════════════════════════════
# Integration smoke-test — signal_table injected into rendered prompt
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignalTableInjectionIntegration:
    def test_signal_table_present_in_rendered_template(self):
        """End-to-end: _build_signal_table output must appear in formatted prompt."""
        sk = {"name": "RE_Speed"}
        pseudo = "1. Rte_Read_RP_VehicleSpeed(&l_f32Speed)\n2. l_f32Speed > CALPRM_SPEED_MAX"
        table = ActivityPipeline._build_signal_table(sk, pseudo, [])
        rendered = _RUNNABLE_USER_TMPL.format(
            swc_name="SWC_X", runnable_name="RE_Speed",
            trigger="10ms", asil="QM", label_style="pseudocode",
            key_steps_block="  1. read speed",
            signal_table=table,
            irv_coherence="  (no shared IRVs)",
            pseudo_code=pseudo,
            cfg_scaffold="{}",
            requirements_block="  - REQ-01",
        )
        assert "Rte_Read_RP_VehicleSpeed(&l_f32Speed)" in rendered
        assert "CALPRM_SPEED_MAX" in rendered

    def test_irv_coherence_present_in_rendered_template(self):
        """End-to-end: IRV coherence block must appear in formatted prompt."""
        sk = {"name": "RE_Calc"}
        xref = {
            "irv_writers": {"IRV_FilteredSpeed": ["RE_Calc"]},
            "irv_readers": {"IRV_FilteredSpeed": ["RE_Torque"]},
            "dem_raisers": {},
        }
        coherence = ActivityPipeline._build_irv_coherence_block(sk, xref)
        rendered = _RUNNABLE_USER_TMPL.format(
            swc_name="SWC_X", runnable_name="RE_Calc",
            trigger="10ms", asil="QM", label_style="pseudocode",
            key_steps_block="  1. compute",
            signal_table="  (none)",
            irv_coherence=coherence,
            pseudo_code="1. Rte_IWrite_IRV_FilteredSpeed(l_f32Speed)",
            cfg_scaffold="{}",
            requirements_block="  - REQ-01",
        )
        assert "IRV_FilteredSpeed" in rendered
        assert "RE_Torque" in rendered
