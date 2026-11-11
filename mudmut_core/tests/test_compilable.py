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
    assert "Rte_Call_RP_Dem_SetEventStatus(MUDMUT_ANY_ARGS);" in hdr
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
