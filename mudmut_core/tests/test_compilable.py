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
