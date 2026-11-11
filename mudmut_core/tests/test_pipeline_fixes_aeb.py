"""Fixes from the DeepSeek AEB run: compile repairs, spec gaps and the targeted spec repair."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from mudmut_core import chain, compilable, design, spec_check


def test_placeholder_type_for_bitmask_and_float():
    code = "irvFault = irvFault | FAULT_BIT;\nif ((irvFlags & BIT_A) != 0U) {}\nirvTimer = 0U;\nirvRamp = 0.0F;"
    assert compilable.placeholder_type("irvFault", code) == "uint32"
    assert compilable.placeholder_type("irvFlags", code) == "uint32"
    assert compilable.placeholder_type("irvTimer", code) == "uint32"
    assert compilable.placeholder_type("irvRamp", code) == "float64"


def test_stdlib_never_stubbed_and_value_helpers_get_types():
    hdr = compilable.generate_rte_swc_header("SWC_X", {"Rte_Read", "Map"}, types={"Map": "float64"})
    assert "float64 Map(MUDMUT_ANY_ARGS);" in hdr
    stubs = compilable.generate_rte_stubs("SWC_X", {"Map"}, types={"Map": "float64"})
    assert "return 0;" in stubs
    assert "#include <math.h>" in compilable.generate_rte_type_header()
    assert "fabsf" in compilable.STDLIB_FUNCS


def _gcc_available() -> bool:
    import shutil
    return shutil.which("gcc") is not None


@pytest.mark.skipif(not _gcc_available(), reason="gcc not available")
def test_make_compilable_keeps_bitmask_logic_and_unstatics_helpers(tmp_path):
    c = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_X.h"\n\n'
        "static void Helper(void);\n\nstatic float32 l_f32D;\nstatic float32 l_f32T;\n\n"
        "void RE_X(void)\n{\n"
        "    irvFault = irvFault | FAULT_BIT_CAL;\n"
        "    if ((irvFault & FAULT_BIT_ACT) != 0U)\n    {\n        irvTimer = irvTimer + 5U;\n    }\n"
        "    l_f32D = fabsf(l_f32T - 1.0F);\n"
        "    l_f32T = Map(l_f32D, 2.0F);\n"
        "    Helper();\n    return;\n}\n\n"
        "static void Helper(void)\n{\n    return;\n}\n"
    )
    rep = compilable.make_compilable(c, "SWC_X", tmp_path)
    assert rep.compile_ok, rep.last_error
    assert rep.stubbed_logic == []
    assert "static void Helper" not in rep.c_code
    rte_h = (tmp_path / "Rte_SWC_X.h").read_text()
    assert "fabsf" not in rte_h                       # comes from <math.h>
    assert "extern uint32 irvFault;" in rte_h
    assert "float64 Map(float64, float64);" in rte_h          # a value-returning helper stays float64 (and is recorded)
    assert "void Helper(void);" in (tmp_path / "SWC_X.h").read_text()   # tests can call it


CAL_SPEC = """### 2.3 Calibration Ports (CalPrm)
| Port | Interface | Type | Default | Range | Description |
|---|---|---|---|---|---|
| RP_CalPrm_PMax | IF_Prm_X | float32 | 250.0 | 100–300 bar | max pressure |
| RP_CalPrm_DevTime | IF_Prm_X | uint16 | 50 | 10–200 ms | persistence |
"""


def test_calprm_defaults_from_spec_table():
    d = compilable.calprm_defaults(CAL_SPEC)
    assert d["RP_CalPrm_PMax"] == ("float32", "250.0")
    assert d["RP_CalPrm_DevTime"] == ("uint16", "50")


@pytest.mark.skipif(not _gcc_available(), reason="gcc not available")
def test_rte_signals_are_settable_variables(tmp_path):
    c = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_X.h"\n\nstatic float32 l_f32In;\n\n'
        "void RE_X(void)\n{\n"
        "    Rte_Read(RP_Demand, &l_f32In);\n"
        "    if (l_f32In > Rte_Prm(RP_CalPrm_PMax))\n    {\n        l_f32In = Rte_Prm(RP_CalPrm_PMax);\n    }\n"
        "    Rte_Write(PP_Pressure, l_f32In);\n    return;\n}\n"
    )
    rep = compilable.make_compilable(c, "SWC_X", tmp_path, spec_md=CAL_SPEC)
    assert rep.compile_ok, rep.last_error
    assert rep.stubbed_statements == 0
    hdr = (tmp_path / "Rte_SWC_X.h").read_text()
    stubs = (tmp_path / "Rte_Stubs.c").read_text()
    assert "#define Rte_Prm(port)" in hdr and "extern float32 Rte_Prm_RP_CalPrm_PMax;" in hdr
    assert "extern float64 Rte_Read_RP_Demand;" in hdr and "extern float64 Rte_Write_PP_Pressure;" in hdr
    assert "float32 Rte_Prm_RP_CalPrm_PMax = 250.0;" in stubs and "void Rte_Stubs_Reset(void)" in stubs
    assert "PP_Pressure;" not in hdr.replace("Rte_Write_PP_Pressure;", "")   # no float64 placeholder for the port
    # A C++ test can set an input and a calibration, run, and check the output.
    test = tmp_path / "t.cpp"
    test.write_text('#include "SWC_X.h"\n#include <cstdio>\n'
                    "int main(){ Rte_Stubs_Reset(); Rte_Read_RP_Demand = 400.0; Rte_Prm(RP_CalPrm_PMax) = 300.0F;"
                    " RE_X(); std::printf(\"%g\\n\", Rte_Write_PP_Pressure);"
                    " return Rte_Write_PP_Pressure == 300.0 ? 0 : 1; }\n")
    import subprocess
    build = subprocess.run(["sh", "-c", f"cd {tmp_path} && gcc -std=c99 -c -I. SWC_X.c Rte_Stubs.c && "
                                        "g++ -I. t.cpp SWC_X.o Rte_Stubs.o -o t && ./t"],
                           capture_output=True, text=True)
    assert build.returncode == 0, build.stderr + build.stdout


def test_fix_loop_guards_against_replies_with_other_files_tests():
    from mudmut_core import verify
    orig = "TEST_GROUP(RE_CommandBrake_Group) {};\nTEST(RE_CommandBrake_Group, A) {}\n"
    wrong = "TEST_GROUP(RE_Init_Group) {};\nTEST(RE_Init_Group, A) {}\n"
    assert verify.same_test_groups(orig, orig.replace("A)", "B)"))
    assert not verify.same_test_groups(orig, wrong)
    log = ("Test_RE_Init.cpp:99:12: error: lvalue required\n  99 | x\n"
           "Test_RE_CommandBrake.cpp:31:12: error: lvalue required\n  31 | y\n")
    only = verify.errors_for_file(log, "Test_RE_CommandBrake.cpp")
    assert "Test_RE_CommandBrake.cpp:31" in only and "Test_RE_Init.cpp" not in only


def test_reset_also_clears_placeholder_irvs():
    stubs = compilable.generate_rte_stubs("SWC_X", set(), variables={"irvTimer"}, types={"irvTimer": "uint32"},
                                          signals={"Read": ["RP_A"], "Write": [], "Prm": []})
    assert stubs.index("uint32 irvTimer = 0;") < stubs.index("void Rte_Stubs_Reset(void)")
    assert "    irvTimer = 0;" in stubs and "    Rte_Read_RP_A = 0;" in stubs


SPEC_WITH_GAPS = """# MUD Spec: SWC_X
## 7. Functional Description
### RE_Init
1. Guard
```c
if (l_eState != MODULE_RESET) {
   return;
}
```
2. Read
```c
ReadInputs();
Rte_Read(RP_A, &l_u8A);
l_f32T = Map(l_u8A);
WdgM_UpdateAliveCounter(WDG_X);
l_f32D = fabsf(l_f32T);
```
"""


def test_spec_check_reports_never_set_and_undescribed_helpers():
    sc = spec_check.check_spec(SPEC_WITH_GAPS, "SWC_X")
    assert sc["ok"]
    assert sc["never_set"] == {"RE_Init": ["l_eState"]}
    assert sc["undescribed_helpers"] == {"RE_Init": ["ReadInputs", "Map"]}   # not WdgM_/Rte_/fabsf
    assert spec_check.gap_count(sc) == 3
    text = " ".join(spec_check.warnings_for(sc, "SWC_X"))
    assert "l_eState" in text and "ReadInputs()" in text
    msgs = [m for _s, m in design.spec_check_issues(sc)]
    assert any("never assigns" in m for m in msgs) and any("inline" in m for m in msgs)


SPEC_TWO_RUNNABLES = SPEC_WITH_GAPS + """### RE_Second
1. Guard
```c
if (l_u8B != 0U) {
   return;
}
```
2. Write
```c
l_u8B = 1U;
Rte_Write(PP_Out, l_u8B);
```
"""


def test_rewrite_problem_detects_a_truncated_spec():
    """Run 20261111_005406: the spec repair rewrote the whole document through an output cap, was cut off
    mid-statement and lost RE_CommandBrake's section; "gaps 2 → 1" made the chain keep it."""
    full = SPEC_TWO_RUNNABLES
    assert spec_check.rewrite_problem(full, full) == ""
    assert spec_check.rewrite_problem(full, full.replace("l_f32D = fabsf(l_f32T);", "l_f32D = 0.0F;")) == ""
    lost = full[: full.index("### RE_Second")]
    assert "RE_Second" in spec_check.rewrite_problem(full, lost)                      # a runnable section vanished
    cut = full[: full.index("l_u8B = 1U;")]
    assert "RE_Second" not in cut or "code block" in spec_check.rewrite_problem(full, cut) \
        or "shorter" in spec_check.rewrite_problem(full, cut)
    unclosed = full.replace("Rte_Write(PP_Out, l_u8B);\n```\n", "Rte_Write(PP_Out, l_u8B")      # ends inside a code block
    assert "code block" in spec_check.rewrite_problem(full, unclosed)
    assert "shorter" in spec_check.rewrite_problem(full + "x" * 4000, full)           # lost more than 20 %
    assert spec_check.rewrite_problem("", full) == ""                                 # nothing to compare with


def test_chain_discards_a_truncated_repair_even_when_it_has_fewer_gaps(tmp_path, monkeypatch):
    calls = {"repair": 0}

    async def fake_plan(text, temperature=0.2):
        return SimpleNamespace(modules=[SimpleNamespace(swc_name="SWC_X", description="x", asil="QM",
                                                        runnables=["RE_Init", "RE_Second"], req_ids=["REQ-001"])],
                               architecture_summary="x")

    async def fake_spec(module, text, mode="two_stage", progress=None):
        return SPEC_TWO_RUNNABLES + "\n" + "Filler text for length. " * 10

    async def fake_repair(module, text, spec_md, check, progress=None):
        calls["repair"] += 1
        # cut off after the first runnable: no gaps left, but RE_Second's section is gone
        return spec_md[: spec_md.index("### RE_Second")].replace("ReadInputs();\n", "")

    async def stop_after_spec(*a, **k):
        raise RuntimeError("stop here")

    monkeypatch.setattr(design, "plan_modules", fake_plan)
    monkeypatch.setattr(design, "generate_mud_spec", fake_spec)
    monkeypatch.setattr(design, "repair_spec_from_check", fake_repair)
    monkeypatch.setattr(design, "generate_activity", stop_after_spec)
    monkeypatch.setattr(chain, "_unload_models", lambda models: None)
    monkeypatch.setattr(chain, "_mud_models", lambda: [])
    req = tmp_path / "r.csv"
    req.write_text("Req_ID,Title,Description,Type,Priority,Safety,Module\n"
                   "REQ-001,T,The SWC shall x,functional,must,QM,SWC_X\n")
    with pytest.raises(RuntimeError):
        asyncio.run(chain.run_full_chain(str(req), swc="SWC_X", quick=True, root=tmp_path / "runs"))
    run_dir = next(d for d in (tmp_path / "runs").iterdir() if d.is_dir())
    assert calls["repair"] == 1
    spec = (run_dir / "01_mud" / "mud_spec.md").read_text()
    assert "### RE_Second" in spec and "ReadInputs" in spec        # the first spec was kept
    assert not (run_dir / "01_mud" / "mud_spec_first.md").exists()
    warnings = json.loads((run_dir / "run.json").read_text())["warnings"]
    assert any("spec repair was discarded" in w and "RE_Second" in w for w in warnings), warnings   # and the report says why


def test_chain_keeps_repaired_spec_only_when_better(tmp_path, monkeypatch):
    good = SPEC_WITH_GAPS.replace("ReadInputs();\n", "").replace("l_f32T = Map(l_u8A);", "l_f32T = l_u8A * 2.0F;") \
        .replace("if (l_eState != MODULE_RESET)", "if (l_u8A != 0U)")
    calls = {"repair": 0}

    async def fake_plan(text, temperature=0.2):
        return SimpleNamespace(modules=[SimpleNamespace(swc_name="SWC_X", description="x", asil="QM",
                                                        runnables=["RE_Init"], req_ids=["REQ-001"])],
                               architecture_summary="x")

    async def fake_spec(module, text, mode="two_stage", progress=None):
        return SPEC_WITH_GAPS + "\n" + "Filler text for length. " * 10

    async def fake_repair(module, text, spec_md, check, progress=None):
        calls["repair"] += 1
        return good + "\n" + "Filler text for length. " * 10

    async def stop_after_spec(*a, **k):
        raise RuntimeError("stop here")

    monkeypatch.setattr(design, "plan_modules", fake_plan)
    monkeypatch.setattr(design, "generate_mud_spec", fake_spec)
    monkeypatch.setattr(design, "repair_spec_from_check", fake_repair)
    monkeypatch.setattr(design, "generate_activity", stop_after_spec)
    monkeypatch.setattr(chain, "_unload_models", lambda models: None)
    monkeypatch.setattr(chain, "_mud_models", lambda: [])
    req = tmp_path / "r.csv"
    req.write_text("Req_ID,Title,Description,Type,Priority,Safety,Module\n"
                   "REQ-001,T,The SWC shall x,functional,must,QM,SWC_X\n")
    with pytest.raises(RuntimeError):
        asyncio.run(chain.run_full_chain(str(req), swc="SWC_X", quick=True, root=tmp_path / "runs"))
    run_dir = next(d for d in (tmp_path / "runs").iterdir() if d.is_dir())
    assert calls["repair"] == 1
    assert "ReadInputs" not in (run_dir / "01_mud" / "mud_spec.md").read_text()
    assert (run_dir / "01_mud" / "mud_spec_first.md").is_file()


def test_swc_never_defines_bsw_services():
    from mudmut_core import compilable
    c = ("Std_ReturnType WdgM_UpdateAliveCounter(float64 a0);  /* see sub-diagram */\n"
         "void RE_Run(void)\n{\n    WdgM_UpdateAliveCounter(1);\n}\n\n"
         "Std_ReturnType WdgM_UpdateAliveCounter(float64 a0)\n{\n    if (a0) { l_x = 1; }\n    return RTE_E_OK;\n}\n\n"
         "void SF_Own(void)\n{\n}\n")
    out, removed = compilable.strip_bsw_definitions(c)
    assert removed == ["WdgM_UpdateAliveCounter"]
    assert "Std_ReturnType WdgM_UpdateAliveCounter" not in out
    assert "    WdgM_UpdateAliveCounter(1);" in out          # the call stays
    assert "void RE_Run(void)" in out and "void SF_Own(void)" in out


def test_a_bare_identifier_statement_is_removed_without_counting_as_stubbed(tmp_path):
    from mudmut_core import compilable
    c = ("#include \"Rte_Type.h\"\nfloat32 l_maxPressure;\nvoid RE_Run(void)\n{\n    l_maxPressure;\n    Guard;\n}\n")
    rep = compilable.make_compilable(c, "SWC_T", c and tmp_path)
    assert "TODO(design): l_maxPressure;" in rep.c_code
    assert rep.stubbed_statements == 1                 # only the prose label Guard; counts


@pytest.mark.skipif(not _gcc_available(), reason="gcc not available")
def test_implicit_sr_value_form_reads_and_writes_the_port_variables(tmp_path):
    """x = Rte_IRead(RP_In) and Rte_IWrite(PP_Out, v) must reach variables a test can set and check."""
    c = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_X.h"\n\nfloat32 l_in;\n\n'
        "void RE_X(void)\n{\n"
        "    l_in = Rte_IRead(RP_In);\n"
        "    if (l_in > 10.0f)\n    {\n        l_in = 10.0f;\n    }\n"
        "    Rte_IWrite(PP_Out, l_in);\n}\n"
    )
    rep = compilable.make_compilable(c, "SWC_X", tmp_path)
    assert rep.compile_ok, rep.last_error
    hdr = (tmp_path / "Rte_SWC_X.h").read_text()
    assert "#define Rte_IRead(port)" in hdr and "#define Rte_IWrite(port, val)" in hdr
    assert "extern float64 Rte_IRead_RP_In;" in hdr and "extern float64 Rte_IWrite_PP_Out;" in hdr
    assert "Std_ReturnType Rte_IRead(float64)" not in hdr           # no longer a status-returning stub
    test = tmp_path / "t.cpp"
    test.write_text('#include "SWC_X.h"\nint main(){ Rte_Stubs_Reset(); Rte_IRead_RP_In = 400.0; RE_X();'
                    " return Rte_IWrite_PP_Out == 10.0 ? 0 : 1; }\n")
    import subprocess
    build = subprocess.run(["sh", "-c", f"cd {tmp_path} && gcc -std=c99 -c -I. SWC_X.c Rte_Stubs.c && "
                                        "g++ -I. t.cpp SWC_X.o Rte_Stubs.o -o t && ./t"],
                           capture_output=True, text=True)
    assert build.returncode == 0, build.stderr + build.stdout


def test_clean_spec_markdown_drops_the_repeated_language_tag_line():
    from mudmut_core import design
    spec = ("**1. Guard**\n```c\nc\nboolean l_a = FALSE;\n```\n\n**2. Read**\n```c\nC\nx = 1;\n```\n"
            "```c\nint c;\n```\n```text\nc\nkeep\n```\n")
    out = design.clean_spec_markdown(spec)
    assert "```c\nboolean l_a = FALSE;" in out and "```c\nx = 1;" in out
    assert "```c\nint c;" in out                       # real code that starts with c… is untouched
    assert "```text\nc\nkeep" in out                   # other languages are not touched
    assert design.clean_spec_markdown(None) == ""


@pytest.mark.skipif(not _gcc_available(), reason="gcc not available")
def test_every_call_of_a_recorded_function_is_kept(tmp_path):
    c = (
        '#include "Rte_Type.h"\n#include "Rte_SWC_X.h"\n\n'
        "void RE_X(void)\n{\n"
        "    Dem_ReportErrorStatus(7, 1);\n"
        "    Dem_ReportErrorStatus(10, 0);\n}\n"
    )
    rep = compilable.make_compilable(c, "SWC_X", tmp_path)
    assert rep.compile_ok, rep.last_error
    assert "extern float64 Dem_ReportErrorStatus_hist_arg0[16];" in (tmp_path / "Rte_SWC_X.h").read_text()
    test = tmp_path / "t.cpp"
    test.write_text('#include "SWC_X.h"\nint main(){ Rte_Stubs_Reset(); RE_X();'
                    " if (Dem_ReportErrorStatus_callCount != 2) return 1;"
                    " if (Dem_ReportErrorStatus_arg0 != 10) return 2;"          # the last call, as before
                    " if (Dem_ReportErrorStatus_hist_arg0[0] != 7 || Dem_ReportErrorStatus_hist_arg1[0] != 1) return 3;"
                    " Rte_Stubs_Reset(); if (Dem_ReportErrorStatus_hist_arg0[0] != 0) return 4; return 0; }\n")
    import subprocess
    build = subprocess.run(["sh", "-c", f"cd {tmp_path} && gcc -std=c99 -c -I. SWC_X.c Rte_Stubs.c && "
                                        "g++ -I. t.cpp SWC_X.o Rte_Stubs.o -o t && ./t"],
                           capture_output=True, text=True)
    assert build.returncode == 0, (build.returncode, build.stderr + build.stdout)
