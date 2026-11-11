from pathlib import Path

from mudmut_core import compilable


def test_rte_type_header_defines_std_types():
    header = compilable.generate_rte_type_header()
    for t in ("uint8", "uint16", "uint32", "uint64", "sint8", "sint32", "float32", "float64", "boolean", "Std_ReturnType"):
        assert f"typedef" in header and t in header


def test_collect_identifiers_finds_rte_and_calls():
    code = "Rte_Read_RP_X(&v); Rte_Write_PP_Y(1); Foo(); if (x) bar();"
    rte, calls = compilable.collect_identifiers(code)
    assert {"Rte_Read_RP_X", "Rte_Write_PP_Y"} <= rte
    assert {"Foo", "bar"} <= calls
    assert "if" not in calls


def test_rte_swc_header_declares_functions():
    header = compilable.generate_rte_swc_header("SWC_Bms", {"Rte_Read_X"}, {"Helper"})
    assert "Std_ReturnType Rte_Read_X(MUDMUT_ANY_ARGS);" in header
    assert "void Helper(MUDMUT_ANY_ARGS);" in header
    assert '#include "Rte_Type.h"' in header


def test_rte_stubs_defines_functions():
    stubs = compilable.generate_rte_stubs("SWC_Bms", {"Rte_Read_X"}, set())
    assert "Std_ReturnType Rte_Read_X()" in stubs
    assert "return E_OK;" in stubs


def test_is_statement_line():
    assert compilable._is_statement_line("    l_u8X = 1;")
    assert compilable._is_statement_line("    if (x)")
    assert not compilable._is_statement_line("static uint8 l_u8X;")  # top-level (no indent)
    assert not compilable._is_statement_line("#include \"Rte_Type.h\"")
    assert not compilable._is_statement_line("/* comment */")
    assert not compilable._is_statement_line("}")


def test_make_compilable_stubs_bad_lines(tmp_path):
    code = (
        '#include "Rte_Type.h"\n'
        '#include "Rte_SWC_Bms.h"\n\n'
        "void RE_Foo(void)\n{\n"
        "    Rte_Read_RP_Speed(&l_u8X);\n"
        "    Compute average of speeds;\n"
        "    l_u8Y = l_u8X;\n"
        "    return;\n"
        "}\n"
    )
    rep = compilable.make_compilable(code, "SWC_Bms", tmp_path)
    assert rep.compile_ok is True
    assert rep.stubbed_statements >= 1
    assert "/* TODO(design): Compute average of speeds; */" in rep.c_code
    assert (tmp_path / "Rte_Type.h").is_file()
    assert (tmp_path / "Rte_SWC_Bms.h").is_file()
    assert (tmp_path / "Rte_Stubs.c").is_file()


def test_make_compilable_keeps_valid_code(tmp_path):
    code = (
        '#include "Rte_Type.h"\n'
        '#include "Rte_SWC_Bms.h"\n\n'
        "static uint8 l_u8X;\n\n"
        "void RE_Foo(void)\n{\n"
        "    l_u8X = 1;\n"
        "    return;\n"
        "}\n"
    )
    rep = compilable.make_compilable(code, "SWC_Bms", tmp_path)
    assert rep.compile_ok is True
    assert rep.stubbed_statements == 0


def test_statement_detection_ignores_trailing_comments():
    assert compilable._is_statement_line("    Guard;  /* Guard */")
    assert compilable._is_statement_line("    x = CONST;  /* [REQ-1] */")
    assert not compilable._is_statement_line("    /* [REQ-1] */")


def test_junk_statements_detected():
    assert compilable._is_junk_statement("    ```c;  /* ```c */")
    assert compilable._is_junk_statement("    Restore defaults;  /* Restore defaults */")
    assert compilable._is_junk_statement("    Validate;")
    assert not compilable._is_junk_statement("    return;")
    assert not compilable._is_junk_statement("    l_u8X = 1;")
    assert not compilable._is_junk_statement("    Rte_Read_X(&l_u8X);")


def test_variable_defined_after_its_first_use_compiles(tmp_path):
    """Run 20261110_235705: ``l_f32Pressure`` was used by one runnable and defined (float32) above a
    later one. The float64 placeholder clashed with it and neither the C nor any test compiled."""
    from mudmut_core import toolchain
    code = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_T.h"\n\n'
        "void RE_First(void)\n{\n    l_f32Pressure = 1.5F;  /* set */\n}\n\n"
        "static float32 l_f32Pressure;\n\n"
        "void RE_Second(void)\n{\n    l_f32Pressure = l_f32Pressure + 1.0F;  /* ramp */\n}\n"
    )
    rep = compilable.make_compilable(code, "SWC_T", tmp_path)
    assert rep.compile_ok, rep.last_error
    assert rep.stubbed_statements == 0 and rep.placeholder_variables == []
    assert "extern float32 l_f32Pressure;" in (tmp_path / "Rte_SWC_T.h").read_text()
    assert "l_f32Pressure" not in (tmp_path / "Rte_Stubs.c").read_text()      # one definition only
    if toolchain.check_toolchain().ok:      # links together with the stubs
        r = toolchain.run_c(["gcc", "-std=c99", "-w", "-c", f"-I{tmp_path}", str(tmp_path / "SWC_T.c"),
                             str(tmp_path / "Rte_Stubs.c")], cwd=str(tmp_path))
        assert r.returncode == 0, r.stderr


def test_explicit_rte_accessors_are_test_variables(tmp_path):
    """``Rte_Read_<port>_<elem>(&x)`` must be controllable by a test like ``Rte_Read(port, &x)`` is.

    Run 20261111_001000: these were stub functions that returned E_OK and wrote nothing, so a test
    could not set an input. The tests wrote ``Rte_Read_RP_Speed_Speed = 10.0F;`` (as the test
    interface note says for signals) and 4 of 9 files were quarantined for "assignment of function".
    """
    from mudmut_core import toolchain
    code = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_T.h"\n\n'
        "static float32 l_f32Speed;\nstatic uint8 l_u8Mode;\n\n"
        "void RE_Run(void)\n{\n"
        "    Rte_Read_RP_Speed_Speed(&l_f32Speed);  /* in */\n"
        "    l_u8Mode = Rte_IRead_RP_Mode_Mode();  /* in */\n"
        "    if (l_u8Mode == 1U)\n    {\n"
        "        Rte_Write_PP_Out_Value(l_f32Speed * 2.0F);  /* out */\n"
        "    }\n"
        "    Rte_Call_RP_Dem_SetEventStatus(1U, 2U);  /* stays a function */\n"
        "}\n"
    )
    rep = compilable.make_compilable(code, "SWC_T", tmp_path)
    assert rep.compile_ok, rep.last_error
    assert rep.stubbed_statements == 0
    hdr = (tmp_path / "Rte_SWC_T.h").read_text()
    for var in ("Rte_Read_RP_Speed_Speed", "Rte_IRead_RP_Mode_Mode", "Rte_Write_PP_Out_Value"):
        assert f"extern float64 {var};" in hdr, var
    assert "Rte_Call_RP_Dem_SetEventStatus(float64, float64);" in hdr          # stays a function, now recorded
    assert "extern uint32 Rte_Call_RP_Dem_SetEventStatus_callCount;" in hdr
    if not toolchain.check_toolchain().ok:
        return
    # A C++ test sets the inputs, runs the runnable, checks the output and resets.
    (tmp_path / "t.cpp").write_text(
        '#include "SWC_T.h"\n'
        "int main(){\n"
        "  Rte_Stubs_Reset();\n"
        "  Rte_Read_RP_Speed_Speed = 10.0F; Rte_IRead_RP_Mode_Mode = 1;\n"
        "  RE_Run();\n"
        "  if (Rte_Write_PP_Out_Value != 20.0) return 1;\n"
        "  Rte_Stubs_Reset();\n"
        "  return (Rte_Write_PP_Out_Value == 0.0 && Rte_Read_RP_Speed_Speed == 0.0) ? 0 : 2; }\n",
        encoding="utf-8")
    for src in ("SWC_T.c", "Rte_Stubs.c"):
        r = toolchain.run_c(["gcc", "-std=c99", "-w", "-c", f"-I{tmp_path}", str(tmp_path / src),
                             "-o", str(tmp_path / (src + ".o"))], cwd=str(tmp_path))
        assert r.returncode == 0, r.stderr
    r = toolchain.run_c(["g++", f"-I{tmp_path}", str(tmp_path / "t.cpp"), str(tmp_path / "SWC_T.c.o"),
                         str(tmp_path / "Rte_Stubs.c.o"), "-o", str(tmp_path / "t")], cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert toolchain.run_c([str(tmp_path / "t")]).returncode == 0


def test_generic_irv_read_write_are_controllable_by_tests(tmp_path):
    """``Rte_IrvRead(IRV_X, &l)`` / ``Rte_IrvWrite(IRV_X, v)`` — the form DeepSeek writes — read and
    write the IRV variable, so a test can set an input and check an output.

    Run 20261111_005406: these were empty stub functions. A test that set ``IRV_FinalBrakePressureCommand
    = 123.5`` never reached the code (the local stayed 0) and 28 of 45 test cases failed with
    "expected <123.5> but was <0>" although the logic was right.
    """
    from mudmut_core import toolchain
    code = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_T.h"\n\n'
        "uint32 l_pressure;\nuint32 l_ready;\n\n"
        "void RE_Cmd(void)\n{\n"
        "    Rte_IrvRead(IRV_Pressure, &l_pressure);  /* in */\n"
        "    Rte_IrvRead(IRV_Ready, &l_ready);  /* in */\n"
        "    if (l_ready == 1U)\n    {\n"
        "        Rte_IrvWrite(IRV_Out, l_pressure);  /* out */\n"
        "    }\n"
        "    Rte_IrvWrite(IRV_Status, 4);  /* out */\n"
        "}\n"
    )
    rep = compilable.make_compilable(code, "SWC_T", tmp_path)
    assert rep.compile_ok, rep.last_error
    assert rep.stubbed_statements == 0 and rep.logic_stubbed == 0
    hdr = (tmp_path / "Rte_SWC_T.h").read_text()
    stubs = (tmp_path / "Rte_Stubs.c").read_text()
    assert "#define Rte_IrvRead(var, dst)" in hdr and "#define Rte_IrvWrite(var, val)" in hdr
    assert "Rte_IrvRead(MUDMUT_ANY_ARGS)" not in hdr      # no function declaration clashing with the macro
    assert "Rte_IrvRead()" not in stubs and "Rte_IrvWrite()" not in stubs
    for var in ("IRV_Pressure", "IRV_Ready", "IRV_Out", "IRV_Status"):
        assert f"extern float64 {var};" in hdr, var
    assert "void Rte_Stubs_Reset(void);" in hdr and "IRV_Out = 0;" in stubs
    if not toolchain.check_toolchain().ok:
        return
    (tmp_path / "t.cpp").write_text(
        '#include "SWC_T.h"\n'
        "int main(){\n"
        "  Rte_Stubs_Reset();\n"
        "  IRV_Pressure = 123.5; IRV_Ready = 1;\n"
        "  RE_Cmd();\n"
        "  if (IRV_Out != 123) return 1;\n"            # float64 value stored through uint32 local
        "  if (IRV_Status != 4) return 2;\n"
        "  Rte_Stubs_Reset();\n"
        "  return (IRV_Out == 0 && IRV_Status == 0) ? 0 : 3; }\n",
        encoding="utf-8")
    for src in ("SWC_T.c", "Rte_Stubs.c"):
        r = toolchain.run_c(["gcc", "-std=c99", "-w", "-c", f"-I{tmp_path}", str(tmp_path / src),
                             "-o", str(tmp_path / (src + ".o"))], cwd=str(tmp_path))
        assert r.returncode == 0, r.stderr
    r = toolchain.run_c(["g++", f"-I{tmp_path}", str(tmp_path / "t.cpp"), str(tmp_path / "SWC_T.c.o"),
                         str(tmp_path / "Rte_Stubs.c.o"), "-o", str(tmp_path / "t")], cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert toolchain.run_c([str(tmp_path / "t")]).returncode == 0


def test_spec_declared_local_types_replace_the_exporters_guess(tmp_path):
    """The exporter guesses a local's type from a Hungarian prefix and falls back to uint32; the spec
    declares the real one (``float32 l_fDecelDemand``).

    Run 20261111_005406: pressures were uint32, so a test's 123.5 was stored as 123 and -10 became
    4294967286 — a wrong value in the C, not in the design.
    """
    spec = (
        "```c\nfloat32 l_fDecelDemand = Rte_IRead(RP_DecelDemand);\n"
        "float32 l_finalPressure = 0.0f;\nuint8 l_counter = 0U;\nboolean l_ok = FALSE;\n```\n"
        "In RE_A: float32 l_mixed; in RE_B: uint8 l_mixed;\n"          # conflicting declarations: leave as is
    )
    assert compilable.spec_local_types(spec) == {
        "l_fDecelDemand": "float32", "l_finalPressure": "float32", "l_counter": "uint8", "l_ok": "boolean"}
    code = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_T.h"\n\n'
        "uint32 l_fDecelDemand;\nuint32 l_finalPressure;\nuint32 l_counter;\nuint32 l_mixed;\nuint32 l_unknown;\n\n"
        "void RE_A(void)\n{\n    l_fDecelDemand = -10.5F;  /* in */\n    l_finalPressure = l_fDecelDemand * 2.0F;\n}\n"
    )
    rep = compilable.make_compilable(code, "SWC_T", tmp_path, spec_md=spec)
    assert rep.compile_ok, rep.last_error
    assert "float32 l_fDecelDemand;" in rep.c_code and "float32 l_finalPressure;" in rep.c_code
    assert "uint8 l_counter;" in rep.c_code
    assert "uint32 l_mixed;" in rep.c_code and "uint32 l_unknown;" in rep.c_code
    assert "extern float32 l_fDecelDemand;" in (tmp_path / "SWC_T.h").read_text()      # tests see the same type


def test_default_typed_locals_used_as_floats_become_float32(tmp_path):
    """A local the spec does not declare keeps the exporter's uint32 default — even when the code
    compares it with ``0.0f`` or takes ``fabsf`` of it (run 20261111_005406, RE_BrakeFeedbackCheck:
    a test's -5.0 feedback wrapped to 4294967291). Usage decides: float literal, float function,
    or an expression of another float local.
    """
    code = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_T.h"\n\n'
        "uint32 l_feedbackPressure;\nuint32 l_commandedPressure;\nuint32 l_deviation;\nuint32 l_absDeviation;\n"
        "uint32 l_debounceCounter;\nuint32 l_u8Mode;\nuint32 l_ready;\nuint32 l_declared;\n\n"
        "void RE_A(void)\n{\n"
        "    Rte_IRead_RP_Feedback_Value(&l_feedbackPressure);\n"
        "    if (l_feedbackPressure < 0.0f)\n    {\n        l_feedbackPressure = 0.0f;\n    }\n"
        "    l_deviation = l_commandedPressure - l_feedbackPressure;\n"
        "    l_absDeviation = fabsf(l_deviation);\n"
        "    l_debounceCounter = l_debounceCounter + 1U;\n"
        "    if (l_u8Mode == 1U && l_ready == TRUE)\n    {\n        l_declared = 5U;\n    }\n"
        "}\n"
    )
    assert compilable.float_locals(code) == {"l_feedbackPressure", "l_commandedPressure", "l_deviation", "l_absDeviation"}
    rep = compilable.make_compilable(code, "SWC_T", tmp_path, spec_md="uint8 l_declared = 0U;")
    assert rep.compile_ok, rep.last_error
    for name in ("l_feedbackPressure", "l_commandedPressure", "l_deviation", "l_absDeviation"):
        assert f"float32 {name};" in rep.c_code, name
    for name in ("l_debounceCounter", "l_ready"):
        assert f"uint32 {name};" in rep.c_code, name          # integer use: unchanged
    assert "uint32 l_u8Mode;" in rep.c_code                    # Hungarian integer prefix: unchanged
    assert "uint8 l_declared;" in rep.c_code                   # the spec's declaration still wins


def test_external_calls_are_recorded_for_tests(tmp_path):
    """Calls to external functions (Dem_*, WdgM_*, ...) can be observed: ``<fn>_callCount`` and the
    last call's ``<fn>_arg<N>``, reset by Rte_Stubs_Reset().

    Run 20261111_005406: requirements such as "report event X to the Dem" could only be tested with
    a mock the model wrote itself — a C++ function the C code never calls — so 11 cases failed
    ("expected <1> but was <0>") although the code did report the event.
    """
    from mudmut_core import toolchain
    code = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_T.h"\n\n'
        "uint32 l_ready;\n\n"
        "void RE_Check(void)\n{\n"
        "    if (l_ready != TRUE)\n    {\n"
        "        Dem_ReportErrorStatus(SWC_DEM_E_InitFailed, DEM_EVENT_STATUS_FAILED);  /* FAULT */\n"
        "        return;\n    }\n"
        "    Dem_ReportErrorStatus(SWC_DEM_E_BadSignal, DEM_EVENT_STATUS_PASSED);\n"
        "    WdgM_TriggerAliveCounter(0);\n"
        "    NvM_WriteBlock(&l_ready);\n"                  # pointer argument: not recorded, stays a plain stub
        "}\n"
    )
    rep = compilable.make_compilable(code, "SWC_T", tmp_path)
    assert rep.compile_ok, rep.last_error
    assert rep.stubbed_statements == 0
    hdr = (tmp_path / "Rte_SWC_T.h").read_text()
    stubs = (tmp_path / "Rte_Stubs.c").read_text()
    for sym in ("Dem_ReportErrorStatus_callCount", "Dem_ReportErrorStatus_arg0", "Dem_ReportErrorStatus_arg1",
                "WdgM_TriggerAliveCounter_callCount", "WdgM_TriggerAliveCounter_arg0"):
        assert f"extern " in hdr and f" {sym};" in hdr, sym
    assert "NvM_WriteBlock_callCount" not in hdr and "NvM_WriteBlock(MUDMUT_ANY_ARGS);" in hdr
    # The two event ids are different constants (an id that is a variable was 0 for every event).
    assert "SWC_DEM_E_InitFailed (" in hdr and "SWC_DEM_E_BadSignal (" in hdr
    assert "Dem_ReportErrorStatus_callCount = 0;" in stubs
    if not toolchain.check_toolchain().ok:
        return
    (tmp_path / "t.cpp").write_text(
        '#include "SWC_T.h"\n'
        "int main(){\n"
        "  Rte_Stubs_Reset();\n"
        "  l_ready = 0; RE_Check();\n"
        "  if (Dem_ReportErrorStatus_callCount != 1) return 1;\n"
        "  if (Dem_ReportErrorStatus_arg0 != SWC_DEM_E_InitFailed || Dem_ReportErrorStatus_arg1 != DEM_EVENT_STATUS_FAILED) return 2;\n"
        "  if (SWC_DEM_E_InitFailed == SWC_DEM_E_BadSignal) return 3;\n"
        "  if (WdgM_TriggerAliveCounter_callCount != 0) return 4;\n"
        "  Rte_Stubs_Reset();\n"
        "  l_ready = 1; RE_Check();\n"
        "  if (Dem_ReportErrorStatus_callCount != 1 || Dem_ReportErrorStatus_arg0 != SWC_DEM_E_BadSignal) return 5;\n"
        "  if (WdgM_TriggerAliveCounter_callCount != 1 || WdgM_TriggerAliveCounter_arg0 != 0) return 6;\n"
        "  Rte_Stubs_Reset();\n"
        "  return (Dem_ReportErrorStatus_callCount == 0 && Dem_ReportErrorStatus_arg0 == 0) ? 0 : 7; }\n",
        encoding="utf-8")
    for src in ("SWC_T.c", "Rte_Stubs.c"):
        r = toolchain.run_c(["gcc", "-std=c99", "-w", "-c", f"-I{tmp_path}", str(tmp_path / src),
                             "-o", str(tmp_path / (src + ".o"))], cwd=str(tmp_path))
        assert r.returncode == 0, r.stderr
    r = toolchain.run_c(["g++", f"-I{tmp_path}", str(tmp_path / "t.cpp"), str(tmp_path / "SWC_T.c.o"),
                         str(tmp_path / "Rte_Stubs.c.o"), "-o", str(tmp_path / "t")], cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    run = toolchain.run_c([str(tmp_path / "t")])
    assert run.returncode == 0, f"exit code {run.returncode}"


BROKEN_C = (
    '#include "Rte_Type.h"\n#include "Rte_SWC_T.h"\n\n'
    "uint32 l_a;\nuint32 l_b;\n\n"
    "/* Requirements: REQ-1 */\n"
    "void RE_One(void)\n{\n"
    "    l_a = 5U;  /* [REQ-1] */\n"
    "    l_b = l_a.value + 1U;  /* member of a plain integer: not C */\n"
    "}\n\n"
    "void RE_Two(void)\n{\n    l_a = 0U;\n}\n"
)


def test_compile_errors_are_sent_to_a_fixer_until_it_compiles(tmp_path):
    """Instead of commenting a failing statement out, the compiler's message goes to the model, which
    returns corrected code; this repeats until the file compiles (user requirement: compile recursively)."""
    seen = []

    def fixer(code, errors, header, note=""):
        seen.append((errors, note))
        return code.replace("l_a.value + 1U", "l_a + 1U")

    rep = compilable.make_compilable(BROKEN_C, "SWC_T", tmp_path, fixer=fixer)
    assert rep.compile_ok, rep.last_error
    assert rep.stubbed_statements == 0 and rep.logic_stubbed == 0     # nothing was commented out
    assert rep.fix_requests == 1 and rep.fixes_applied == 1
    assert "l_b = l_a + 1U;" in rep.c_code
    assert "error" in seen[0][0] and "SWC_T.c" in seen[0][0]            # the compiler message reached the fixer
    assert "fix request" in rep.summary()


def test_second_fix_round_when_the_first_answer_only_partly_helps(tmp_path):
    code = BROKEN_C.replace("    l_a = 5U;  /* [REQ-1] */\n",
                            "    l_a = 5U;  /* [REQ-1] */\n    l_a = l_a.other;\n")
    answers = iter([lambda c: c.replace("l_b = l_a.value + 1U;", "l_b = l_a + 1U;"),       # fixes one of two errors
                    lambda c: c.replace("l_a = l_a.other;", "l_a = l_a;")])
    def fixer(c, errors, header, note=""):
        return next(answers)(c)
    rep = compilable.make_compilable(code, "SWC_T", tmp_path, fixer=fixer)
    assert rep.compile_ok and rep.fix_requests == 2 and rep.fixes_applied == 2 and rep.stubbed_statements == 0


def test_a_fix_that_loses_a_function_or_a_requirement_comment_is_rejected(tmp_path):
    def drops_function(c, errors, header, note=""):
        return c.split("void RE_Two")[0].replace("l_a.value", "l_a")          # RE_Two disappeared

    rep = compilable.make_compilable(BROKEN_C, "SWC_T", tmp_path, fixer=drops_function)
    assert rep.fixes_applied == 0 and rep.fix_requests >= 1
    assert "void RE_Two" in rep.c_code                                          # the original was kept
    assert rep.compile_ok and rep.stubbed_statements == 1 and rep.logic_stubbed == 1   # old fallback: comment out, flagged

    def drops_comment(c, errors, header, note=""):
        return c.replace("/* Requirements: REQ-1 */", "").replace("/* [REQ-1] */", "").replace("l_a.value", "l_a")

    rep = compilable.make_compilable(BROKEN_C, "SWC_T", tmp_path / "b", fixer=drops_comment)
    assert rep.fixes_applied == 0 and "REQ-1" in rep.c_code


def test_fixer_that_makes_no_progress_is_not_asked_forever(tmp_path):
    calls = []

    def useless(c, errors, header, note=""):
        calls.append(note)
        return c                                                                  # same code, same errors

    rep = compilable.make_compilable(BROKEN_C, "SWC_T", tmp_path, fixer=useless)
    assert len(calls) == 2 and rep.fix_requests == 2 and rep.fixes_applied == 0   # stops after two answers without progress
    assert calls[1] and "no" in calls[1].lower()                                  # the second request says why the first was refused
    assert rep.compile_ok and rep.logic_stubbed == 1


def test_fixer_errors_fall_back_to_commenting_out(tmp_path):
    def broken(c, errors, header, note=""):
        raise RuntimeError("provider down")

    rep = compilable.make_compilable(BROKEN_C, "SWC_T", tmp_path, fixer=broken)
    assert rep.compile_ok and rep.fixes_applied == 0 and rep.logic_stubbed == 1


def test_call_arities_need_one_plain_shape():
    code = ("Dem_Report(A_B_C, 1); Dem_Report(A_B_D, 2); Wdg(0); Wdg(1, 2); Nv(&x); "
            "Str(\"s\"); Zero(); Zero(); Nest(f(1)); Member(a.b);")
    got = compilable.call_arities(code, {"Dem_Report", "Wdg", "Nv", "Str", "Zero", "Nest", "Member", "Missing"})
    assert got == {"Dem_Report": 2, "Zero": 0}          # mixed arity, pointer, string, nested call, member: no recorder


def test_enum_like_names_are_constants_not_variables():
    for name in ("SWC_DEM_E_ActuatorInitFailed", "DEM_EVENT_STATUS_FAILED", "ACT_FAULT_DEVIATION", "DEM_E_Foo"):
        assert compilable._is_constant_name(name), name
    for name in ("IRV_TargetBrakePressure", "RP_CalPrm_KVehMass", "l_fPressure", "irvState", "Rte_Foo_Bar", "WdgM_Update"):
        assert not compilable._is_constant_name(name), name


def test_irv_macros_only_when_used_in_the_two_argument_form():
    assert compilable.irv_macros("Rte_IrvRead(IRV_A, &l_x); Rte_IrvWrite(IRV_B, 1);").keys() == {"Rte_IrvRead", "Rte_IrvWrite"}
    assert compilable.irv_macros("/* Rte_IrvRead(IRV_A, &x) */ int y;") == {}               # only in a comment
    assert compilable.irv_macros("Rte_IrvRead_RP_A_B(&x);") == {}                            # the suffixed form is an accessor
    assert compilable.irv_macros("Rte_IrvRead(IRV_A);") == {}                                # shape the macro cannot serve
    assert compilable.irv_macros("Rte_IrvWrite(IRV_A, 1); Rte_IrvWrite(IRV_B);") == {}       # inconsistent use: keep the function


def test_declarations_are_not_prose():
    """``uint8 count;`` is two words like ``Restore defaults;`` but it is C and must be kept."""
    for decl in ("    uint8 count;", "    float32 l_f32Tmp;", "    static const uint16 limit;",
                 "    Object_t obj;", "    Dem_EventStatusType status;", "    unsigned int n;"):
        assert not compilable._is_junk_statement(decl), decl
    assert not compilable._is_junk_statement("    Track track;", {"Track"})     # typedef'd in the file
    for prose in ("    Guard;", "    Restore defaults;", "    Compute average of speeds;", "    Track track;"):
        assert compilable._is_junk_statement(prose), prose


def test_make_compilable_declares_instead_of_deleting(tmp_path):
    code = (
        '#include "Rte_Type.h"\n'
        '#include "Rte_SWC_Other.h"\n\n'        # include under a different SWC name
        "/* Local variables */\n"
        "static uint8 l_u8Mode;\n\n"
        "void RE_Init(void)\n{\n"
        "    /* [REQ-BMS-001] */\n"
        "    ```c;  /* ```c */\n"
        "    irvContactorState = CONTACTOR_OPEN;  /* set */\n"
        "    l_u8Mode = MODE_INIT;  /* mode */\n"
        "    EKF_Predict(&l_u8Mode);  /* helper */\n"
        "    Guard;  /* Guard */\n"
        "    return;\n"
        "}\n"
    )
    rep = compilable.make_compilable(code, "SWC_Bms", tmp_path)
    assert rep.compile_ok is True, rep.last_error
    # real statements kept, only fence + prose stubbed
    assert "irvContactorState = CONTACTOR_OPEN;" in rep.c_code
    assert "l_u8Mode = MODE_INIT;" in rep.c_code
    assert "    EKF_Predict(&l_u8Mode);" in rep.c_code
    assert rep.stubbed_statements == 2
    assert set(rep.placeholder_constants) == {"CONTACTOR_OPEN", "MODE_INIT"}
    assert rep.placeholder_variables == ["irvContactorState"]
    # placeholder constants get distinct values
    hdr = (tmp_path / "Rte_SWC_Bms.h").read_text()
    assert "#define CONTACTOR_OPEN (1)" in hdr and "#define MODE_INIT (2)" in hdr
    # file-scope design variable exposed to tests through <SWC>.h
    assert "static uint8 l_u8Mode" not in rep.c_code
    swc_h = (tmp_path / "SWC_Bms.h").read_text()
    assert "void RE_Init(void);" in swc_h and "extern uint8 l_u8Mode;" in swc_h
    assert (tmp_path / "Rte_SWC_Other.h").is_file()


def test_test_header_exports_the_constants_and_types_the_c_file_defines(tmp_path):
    """A test must see the same constant values and struct types as the C file.

    Seen on the AEB run: the C file defined ``TTC_CRITICAL (0.6F)`` itself, the tests got the
    placeholder ``TTC_CRITICAL (9000)`` from the Rte header, and failed on a wrong expected value;
    a struct typedef'd in the C file was unknown to the tests.
    """
    from mudmut_core import toolchain
    code = (
        '#include "Rte_Type.h"\n'
        "#ifndef TTC_CRITICAL\n#define TTC_CRITICAL (0.6F)  /* s */\n#endif\n"
        "#define MAX_OBJ 4U\n"
        "#define SQUARE(x) ((x) * (x))\n"                       # function-like: stays private
        "typedef struct { float32 distance; uint8 id; } Object_t;\n"
        "typedef struct {\n    uint8 count;\n    Object_t objects[MAX_OBJ];\n} ObjectList_t;\n"
        '#include "Rte_SWC_T.h"\n\n'
        "static float32 l_f32Prob;\n\n"
        "void RE_Risk(void)\n{\n"
        "    l_f32Prob = (irvTtc < TTC_CRITICAL) ? 1.0F : 0.0F;  /* risk */\n"
        "}\n"
    )
    rep = compilable.make_compilable(code, "SWC_T", tmp_path)
    swc_h = (tmp_path / "SWC_T.h").read_text()
    assert "#define TTC_CRITICAL (0.6F)" in swc_h and "#define MAX_OBJ 4U" in swc_h
    assert "SQUARE" not in swc_h
    assert "} ObjectList_t;" in swc_h and "Object_t;" in swc_h
    # the C file's value wins over any placeholder in the Rte header
    assert swc_h.index("#define TTC_CRITICAL") < swc_h.index('#include "Rte_SWC_T.h"')
    if not toolchain.check_toolchain().ok:
        return
    assert rep.compile_ok, rep.last_error
    (tmp_path / "t.cpp").write_text(
        '#include "SWC_T.h"\n'
        "int main(){ ObjectList_t l; l.count = 1; l.objects[0].id = 2;\n"
        "  return (TTC_CRITICAL > 0.5F && TTC_CRITICAL < 0.7F && l.count == 1) ? 0 : 1; }\n", encoding="utf-8")
    r = toolchain.run_c(["g++", "-I" + str(tmp_path), str(tmp_path / "t.cpp"), "-o", str(tmp_path / "t")])
    assert r.returncode == 0, r.stderr
    assert toolchain.run_c([str(tmp_path / "t")]).returncode == 0


def test_rte_stubs_callable_with_arguments_from_cpp(tmp_path):
    """C++ tests must be able to call the C stubs with arguments and link."""
    from mudmut_core import toolchain
    if not toolchain.check_toolchain().ok:
        import pytest
        pytest.skip("C/C++ toolchain not available")
    (tmp_path / "Rte_Type.h").write_text(compilable.generate_rte_type_header(), encoding="utf-8")
    (tmp_path / "Rte_SWC_X.h").write_text(
        compilable.generate_rte_swc_header("SWC_X", {"Rte_Read_RP_X"}, {"EKF_Predict"}), encoding="utf-8")
    (tmp_path / "Rte_Stubs.c").write_text(
        compilable.generate_rte_stubs("SWC_X", {"Rte_Read_RP_X"}, {"EKF_Predict"}), encoding="utf-8")
    (tmp_path / "t.cpp").write_text(
        '#include "Rte_SWC_X.h"\nint main(){ int v=0; Rte_Read_RP_X(&v); EKF_Predict(1, 2.0); return 0; }\n',
        encoding="utf-8")
    r = toolchain.run_c(["gcc", "-std=c99", "-c", str(tmp_path / "Rte_Stubs.c"), "-o", str(tmp_path / "s.o")])
    assert r.returncode == 0, r.stderr
    r = toolchain.run_c(["g++", "-I" + str(tmp_path), str(tmp_path / "t.cpp"), str(tmp_path / "s.o"), "-o", str(tmp_path / "t")])
    assert r.returncode == 0, r.stderr
