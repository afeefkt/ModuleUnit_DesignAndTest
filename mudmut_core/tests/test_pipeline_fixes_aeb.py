"""Fixes from the DeepSeek AEB run: compile repairs, spec gaps and the targeted spec repair."""

import asyncio
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
    assert "float64 Map(MUDMUT_ANY_ARGS);" in rte_h
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
