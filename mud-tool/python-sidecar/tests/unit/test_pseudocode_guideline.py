"""Tests for Phase PSEUDO: strict Section 7 pseudo-code enforcement.

Covers:
  P-1: pseudocode_guideline.py constants are well-formed
  P-2: _GEN_SYSTEM_PROMPT has the golden rule at top + final reminder at bottom
  P-3: _normalize_with_auto_repair triggers _repair_section7_prose ONCE on prose
  P-3 (loop guard): repair runs at most once even if 2nd pass still has prose
  P-4: Stage 3 per-runnable retry fires when prose is detected
  P-6: _REGEN_SYSTEM_PROMPT and _SECTION7_SYSTEM contain the golden rule
"""

from __future__ import annotations

import pytest

from mudtool.ai.pseudocode_guideline import (
    BEFORE_AFTER_EXAMPLE,
    FINAL_REMINDER,
    LOCAL_VAR_NAMING,
    PSEUDO_CODE_GOLDEN_RULE,
    REQUIRED_API_PATTERNS,
    SECTION7_GUIDELINE_BLOCK,
)


# ─── P-1 — pseudocode_guideline.py constants ──────────────────────────────────

class TestGuidelineConstants:
    def test_golden_rule_mentions_fenced_code_block(self):
        assert "```c" in PSEUDO_CODE_GOLDEN_RULE
        assert "HIGHEST PRIORITY" in PSEUDO_CODE_GOLDEN_RULE
        assert "REJECTED" in PSEUDO_CODE_GOLDEN_RULE
        assert "REGENERATED" in PSEUDO_CODE_GOLDEN_RULE

    def test_required_api_patterns_lists_core_apis(self):
        for api in ("Rte_Read", "Rte_Write", "Rte_IrvRead", "Rte_IrvWrite",
                    "Rte_Prm", "Dem_ReportErrorStatus", "WdgM_UpdateAliveCounter"):
            assert api in REQUIRED_API_PATTERNS

    def test_local_var_naming_covers_common_types(self):
        for prefix in ("l_f32", "l_u8", "l_u16", "l_bool", "l_e"):
            assert prefix in LOCAL_VAR_NAMING

    def test_before_after_example_shows_rejected_and_required(self):
        assert "❌ REJECTED" in BEFORE_AFTER_EXAMPLE
        assert "✅ REQUIRED" in BEFORE_AFTER_EXAMPLE
        # Required block must contain a fenced ```c block
        assert "```c" in BEFORE_AFTER_EXAMPLE
        # And concrete Rte_ calls
        assert "Rte_Read" in BEFORE_AFTER_EXAMPLE or "Rte_Prm" in BEFORE_AFTER_EXAMPLE

    def test_final_reminder_repeats_priority_message(self):
        assert "FINAL REMINDER" in FINAL_REMINDER
        assert "AUTOMATIC REGENERATION" in FINAL_REMINDER
        assert "```c" in FINAL_REMINDER

    def test_combined_block_includes_all_sections(self):
        assert PSEUDO_CODE_GOLDEN_RULE in SECTION7_GUIDELINE_BLOCK
        assert REQUIRED_API_PATTERNS in SECTION7_GUIDELINE_BLOCK
        assert LOCAL_VAR_NAMING in SECTION7_GUIDELINE_BLOCK
        assert BEFORE_AFTER_EXAMPLE in SECTION7_GUIDELINE_BLOCK


# ─── P-2 + P-6 — Prompt sandwich pattern ──────────────────────────────────────

class TestPromptSandwichPattern:
    def test_gen_system_prompt_starts_with_golden_rule(self):
        from mudtool.ai.mud_spec_generator import _GEN_SYSTEM_PROMPT
        # Golden rule must appear in the FIRST 2000 chars (priority position)
        assert "🚨 SECTION 7 PSEUDO-CODE" in _GEN_SYSTEM_PROMPT[:2000]

    def test_gen_system_prompt_ends_with_final_reminder(self):
        from mudtool.ai.mud_spec_generator import _GEN_SYSTEM_PROMPT
        # Final reminder must appear in the LAST 2000 chars
        assert "FINAL REMINDER" in _GEN_SYSTEM_PROMPT[-2000:]

    def test_gen_system_prompt_template_uses_fenced_blocks(self):
        from mudtool.ai.mud_spec_generator import _GEN_SYSTEM_PROMPT
        # Template should contain ```c fences (P-2 change wrapped indented code)
        assert "```c" in _GEN_SYSTEM_PROMPT
        # Should still contain RTE calls in the template
        assert "Rte_Read(RP_" in _GEN_SYSTEM_PROMPT
        assert "Rte_Write(PP_" in _GEN_SYSTEM_PROMPT

    def test_regen_system_prompt_has_golden_rule(self):
        from mudtool.ai.mud_spec_generator import _REGEN_SYSTEM_PROMPT
        assert "🚨 SECTION 7 PSEUDO-CODE" in _REGEN_SYSTEM_PROMPT

    def test_section7_system_has_golden_rule_and_final_reminder(self):
        from mudtool.ai.mud_pipeline_stages import _SECTION7_SYSTEM
        assert "🚨 SECTION 7 PSEUDO-CODE" in _SECTION7_SYSTEM[:2000]
        assert "FINAL REMINDER" in _SECTION7_SYSTEM[-2000:]


# ─── P-3 — Auto-regen gate fires when prose detected ──────────────────────────

class TestAutoRepairGate:
    def test_apply_normalization_signals_repair_when_prose_detected(self):
        """When auto_repair_context dict is supplied and prose is found,
        the context is mutated with needs_repair=True + flagged_steps."""
        from mudtool.ai.mud_spec_generator import MudSpecGenerator

        # Create a generator with a stub orchestrator (we never call AI)
        class _StubOrchestrator:
            pass
        gen = MudSpecGenerator(_StubOrchestrator())

        prose_md = (
            "## 7. Functional Description\n\n"
            "### RE_Test\n"
            "1. Compute output\n"
            "   Perform the computation and update the output.\n"
        )
        ctx: dict = {"repaired": False}
        gen._apply_section7_normalization(
            prose_md, swc_name="SWC_Test",
            auto_repair_context=ctx,
        )
        assert ctx.get("needs_repair") is True
        assert isinstance(ctx.get("flagged_steps"), list)
        assert len(ctx["flagged_steps"]) >= 1

    def test_apply_normalization_does_not_signal_repair_when_clean(self):
        from mudtool.ai.mud_spec_generator import MudSpecGenerator

        class _StubOrchestrator:
            pass
        gen = MudSpecGenerator(_StubOrchestrator())

        clean_md = (
            "## 7. Functional Description\n\n"
            "### RE_Test\n"
            "1. Read input\n"
            "   Rte_Read(RP_Speed, &l_f32Speed);\n"
            "2. Validate\n"
            "   if (l_f32Speed > 100.0F) { return; }\n"
        )
        ctx: dict = {"repaired": False}
        gen._apply_section7_normalization(
            clean_md, swc_name="SWC_Test",
            auto_repair_context=ctx,
        )
        assert ctx.get("needs_repair") is not True

    def test_apply_normalization_skips_repair_signal_when_already_repaired(self):
        """Loop guard: if context.repaired is True, do NOT signal another repair."""
        from mudtool.ai.mud_spec_generator import MudSpecGenerator

        class _StubOrchestrator:
            pass
        gen = MudSpecGenerator(_StubOrchestrator())

        prose_md = (
            "## 7. Functional Description\n\n"
            "### RE_Test\n"
            "1. Compute output\n"
            "   Perform the computation.\n"
        )
        ctx: dict = {"repaired": True}   # already repaired once
        gen._apply_section7_normalization(
            prose_md, swc_name="SWC_Test",
            auto_repair_context=ctx,
        )
        # Should NOT trigger a 2nd repair even though prose is still present
        assert ctx.get("needs_repair") is not True

    def test_repair_section7_prose_method_exists_and_is_async(self):
        from mudtool.ai.mud_spec_generator import MudSpecGenerator
        import inspect
        assert hasattr(MudSpecGenerator, "_repair_section7_prose")
        assert inspect.iscoroutinefunction(MudSpecGenerator._repair_section7_prose)
        assert hasattr(MudSpecGenerator, "_normalize_with_auto_repair")
        assert inspect.iscoroutinefunction(MudSpecGenerator._normalize_with_auto_repair)


# ─── P-4 — Stage 3 per-runnable prose retry exists ────────────────────────────

class TestStage3ProseRetry:
    def test_stage3_section7_uses_prose_detector(self):
        """Verify Stage 3 imports _step_body_is_pure_prose for retry logic."""
        import inspect
        from mudtool.ai import mud_pipeline_stages
        src = inspect.getsource(mud_pipeline_stages._stage3_section7) \
            if hasattr(mud_pipeline_stages, "_stage3_section7") \
            else inspect.getsource(mud_pipeline_stages.MudSpecPipeline._stage3_section7)
        assert "_step_body_is_pure_prose" in src
        assert "PREVIOUS ATTEMPT REJECTED" in src
        # Retry uses stronger prompt with golden rule + before/after
        assert "_PSEUDO_GOLDEN_RULE" in src
        assert "_PSEUDO_BEFORE_AFTER" in src
