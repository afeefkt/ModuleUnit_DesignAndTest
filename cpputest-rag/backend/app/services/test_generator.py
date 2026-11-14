"""Test generation — LLM prompt construction and CppUTest code generation"""

import aiohttp
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

from app.models import FunctionInfo
from app.config import config
from app.services.c_parser import analyze_c_project
from app.services.rag_engine import retrieve_similar_examples

logger = logging.getLogger(__name__)


import re

_SYM_DEFINE_RE = re.compile(r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)[ \t]+([^\n/]*)", re.MULTILINE)
_SYM_EXTERN_RE = re.compile(r"^[ \t]*extern[ \t]+([\w \t\*]+?)[ \t]+(\w+)[ \t]*;", re.MULTILINE)
_SYM_SKIP = ("_H", "MUDMUT_ANY_ARGS", "TRUE", "FALSE", "E_OK", "E_NOT_OK", "NULL")


# Calls to other functions (Dem_*, NvM_*, WdgM_*, Rte_Call_*) are recorded by the generated stubs
# (mudmut_core.compilable). A mock the model writes itself is a C++ symbol the C code never calls,
# so a test that checks it fails ("expected <1> but was <0>") even when the code is right.
CALL_RECORDER_HINT = (
    "   Calls to other functions (Dem_*, NvM_*, WdgM_*, Rte_Call_*, helpers) are recorded for you. After the call\n"
    "   CHECK <function>_callCount (calls since Rte_Stubs_Reset) and <function>_arg0, <function>_arg1 ...\n"
    "   (the arguments of the LAST call), e.g.\n"
    "   LONGS_EQUAL(1, Dem_ReportErrorStatus_callCount);\n"
    "   LONGS_EQUAL(SWC_DEM_E_ActuatorFault, (long)Dem_ReportErrorStatus_arg0);\n"
    "   Use only the <function>_callCount / <function>_arg<N> names listed in AVAILABLE SYMBOLS.\n"
    "   Read the function source for what each path calls: a monitor usually reports a fault with\n"
    "   DEM_EVENT_STATUS_FAILED on the bad path AND DEM_EVENT_STATUS_PASSED on the healthy path (and may check\n"
    "   several events in one run). So never assert Dem_ReportErrorStatus_callCount == 0 for valid input unless the\n"
    "   source really has no report on that path; count the reports the path makes and CHECK the LAST call's\n"
    "   arguments (arg1 is DEM_EVENT_STATUS_PASSED / DEM_EVENT_STATUS_FAILED). When one run reports several events,\n"
    "   every call is kept: <function>_hist_arg<N>[k] is argument N of the k-th call (k = 0 is the first), e.g.\n"
    "   LONGS_EQUAL(SWC_DEM_E_X, (long)Dem_ReportErrorStatus_hist_arg0[0]);\n"
    "   LONGS_EQUAL(DEM_EVENT_STATUS_FAILED, (long)Dem_ReportErrorStatus_hist_arg1[0]);\n"
    "   Never define your own mock or stub of these functions (no redefinition, no extern \"C\" body, no call counter\n"
    "   of your own): the code under test would call the real stub, not yours."
)


_IO_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
_IO_IN = (
    (re.compile(r"\bRte_Irv(?:I?Read)\s*\(\s*(\w+)\s*,"), "{0}"),
    (re.compile(r"\bRte_Read\s*\(\s*(\w+)\s*,"), "Rte_Read_{0}"),
    (re.compile(r"\bRte_Prm\s*\(\s*(\w+)\s*\)"), "Rte_Prm_{0}"),
    (re.compile(r"\b(Rte_I?Read_\w+)\s*\("), "{0}"),
)
_IO_OUT = (
    (re.compile(r"\bRte_Irv(?:I?Write)\s*\(\s*(\w+)\s*,"), "{0}"),
    (re.compile(r"\bRte_Write\s*\(\s*(\w+)\s*,"), "Rte_Write_{0}"),
    (re.compile(r"\b(Rte_I?Write_\w+)\s*\("), "{0}"),
)


_DEM_REPORT_RE = re.compile(r"\bDem_ReportErrorStatus\s*\(\s*([^,()]+?)\s*,\s*([^()]+?)\s*\)")


def dem_reports(source_code: str) -> list[str]:
    """``["EVENT, STATUS", ...]`` of the Dem reports in the source, each distinct pair once, in order."""
    code = _IO_COMMENT_RE.sub(" ", source_code or "")
    return list(dict.fromkeys(f"{ev}, {st}" for ev, st in _DEM_REPORT_RE.findall(code)))


def function_io(source_code: str, symbols: str = "") -> dict:
    """The exact variables a test must set / check for one function, read from its own source.

    ``set``: variables the function reads (inputs, calibration, IRVs); ``check``: variables it writes;
    ``calls``: functions it calls that have a call recorder (``<fn>_callCount`` in ``symbols``).
    The model otherwise picks a plausible but different accessor name and the test never reaches the
    path it is about.
    """
    code = _IO_COMMENT_RE.sub(" ", source_code or "")

    def collect(rules) -> list[str]:
        found: list[tuple[int, str]] = []
        for rx, fmt in rules:
            found += [(m.start(), fmt.format(m.group(1))) for m in rx.finditer(code)]
        return list(dict.fromkeys(name for _pos, name in sorted(found)))

    called = list(dict.fromkeys(m.group(1) for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", code)))
    return {
        "set": collect(_IO_IN),
        "check": collect(_IO_OUT),
        "calls": [f for f in called if f"{f}_callCount" in (symbols or "")],
        "dem": dem_reports(source_code) if "Dem_ReportErrorStatus_callCount" in (symbols or "") else [],
    }


def function_io_block(io: dict) -> str:
    """Prompt text for :func:`function_io` ("" when the function uses none of them)."""
    lines = []
    if io["set"]:
        lines.append("  set before the call:  " + ", ".join(io["set"]))
    if io["check"]:
        lines.append("  check after the call: " + ", ".join(io["check"]))
    if io["calls"]:
        lines.append("  calls recorded (<fn>_callCount, <fn>_arg0 ...): " + ", ".join(io["calls"]))
    if io.get("dem"):
        lines.append("  Dem_ReportErrorStatus calls in its source (event, status): " + "; ".join(io["dem"]))
        lines.append("  Both FAILED and PASSED reports exist for an event: the healthy path still reports PASSED, so "
                     "Dem_ReportErrorStatus_callCount is NOT 0 there. Read the path you test, count the reports it "
                     "makes, and check the k-th one with Dem_ReportErrorStatus_hist_arg0[k] / _hist_arg1[k].")
    if not lines:
        return ""
    return ("\nTHIS FUNCTION'S TEST INTERFACE (exact variable names, taken from its source; "
            "set / check these and no other variable for the same signal):\n" + "\n".join(lines) + "\n")


def available_symbols(source_file: Path, limit: int = 120) -> str:
    """Constants (with values) and variables a test of ``source_file`` can use.

    Read from the C file and the generated headers next to it. The model only sees one function;
    without this list it invents names such as STATUS_NOT_READY next to STATUS_READY, and the
    test file does not compile.
    """
    source_file = Path(source_file)
    constants: dict[str, str] = {}
    variables: dict[str, str] = {}
    files = [source_file] + sorted(source_file.parent.glob("*.h"))
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, value in _SYM_DEFINE_RE.findall(text):
            value = value.strip()
            if value and not name.endswith("_H") and name not in _SYM_SKIP and "(" not in name:
                constants.setdefault(name, value)
        if f.suffix == ".h":
            for ctype, name in _SYM_EXTERN_RE.findall(text):
                variables.setdefault(name, " ".join(ctype.split()))
    lines = [f"  #define {n} {v}" for n, v in constants.items()][:limit]
    lines += [f"  {t} {n};" for n, t in variables.items()][:limit]
    return "\n".join(lines)


async def generate_cpputest(function_info: FunctionInfo, examples: List[Dict]) -> str:
    """Generate CppUTest case using CodeLlama"""
    symbols = available_symbols(Path(function_info.file_path)) if getattr(function_info, "file_path", None) else ""
    symbols_block = (
        "\nAVAILABLE SYMBOLS (already declared — the only constants and variables that exist):\n"
        f"{symbols}\n"
        "For \"a value different from X\" write (X + 1); never make up a new constant name.\n"
    ) if symbols else ""
    symbols_block += function_io_block(function_io(function_info.source_code, symbols))

    # Build context from examples
    examples_context = "\n\n".join([
        f"Example {i+1}:\n{ex['text']}"
        for i, ex in enumerate(examples[:2])
    ])

    # Build parameters string
    params_str = ', '.join([f"{p['type']} {p['name']}" for p in function_info.parameters])

    prompt = f"""You are an expert C/C++ developer specializing in writing CppUTest unit tests.

Generate a complete CppUTest test case for the following C function.

FUNCTION TO TEST:
```c
{function_info.source_code}
```

Function Details:
- Name: {function_info.name}
- Return Type: {function_info.return_type}
- Parameters: {params_str}
- Complexity Score: {function_info.complexity_score}
{symbols_block}
REFERENCE TEST EXAMPLES:
{examples_context}

REQUIREMENTS:
1. Create a complete CppUTest test group for this function
2. Include setup() and teardown() methods
3. Write at least 3-5 test cases covering:
   - Normal/expected behavior
   - Edge cases
   - Error conditions (if applicable)
   - Boundary values
4. Use appropriate CppUTest macros (CHECK, CHECK_EQUAL, LONGS_EQUAL, STRCMP_EQUAL, etc.)
5. RTE signals are plain variables (declared for you):
   - inputs:      set  Rte_Read_<port>   before the call, e.g. Rte_Read_RP_BrakeDemand = 4.0;
                  (the code's Rte_IRead(<port>) reads the variable Rte_IRead_<port>: set that one instead)
   - calibration: set  Rte_Prm_<port>    (starts at the MUD default), e.g. Rte_Prm_RP_CalPrm_PMax = 250.0F;
   - outputs:     CHECK Rte_Write_<port> after the call, e.g. DOUBLES_EQUAL(0.0, Rte_Write_PP_BrakePressure, 1e-6);
                  (Rte_IWrite(<port>, v) stores into Rte_IWrite_<port>: check that variable)
   - call Rte_Stubs_Reset(); in setup() so every test starts from the defaults.
   The same for accessors with an element name: when the function calls Rte_Read_<port>_<elem>(&x),
   x = Rte_IRead_<port>_<elem>() or Rte_Write_<port>_<elem>(v), then Rte_Read_<port>_<elem>,
   Rte_IRead_<port>_<elem> and Rte_Write_<port>_<elem> are variables you set / check in the same way,
   e.g. Rte_Read_RP_Speed_Speed = 10.0; ... DOUBLES_EQUAL(20.0, Rte_Write_PP_Out_Value, 1e-6);
   Never call these accessors from the test and never compare them with a function call.
{CALL_RECORDER_HINT}
   Test through inputs and outputs: set the variables the function reads, call it, then CHECK
   the variables it writes
6. Add comments explaining what each test validates
7. Follow the style and structure of the reference examples
8. Use ONLY identifiers that appear in the function source above, the signal variables of rule 5
   (Rte_Read_<port> / Rte_Prm_<port> / Rte_Write_<port> for ports the function uses, Rte_Stubs_Reset),
   or standard C/CppUTest names.
   Never invent constants, variables, structs or functions. The function under test and the
   variables it uses are already declared for you; do not redeclare them or add #include lines.

Generate ONLY the test code, starting with TEST_GROUP and including all test cases.
Do not include explanations or markdown formatting - just the C++ test code."""

    try:
        # Route through the multi-provider client using the ``test_generator``
        # stage (provider + model from mudmut_core.agents).
        from mudmut_core.llm import achat, get_providers
        provider_id, model = "ollama", config.GEN_MODEL
        try:
            from mudmut_core import agents
            st = agents.get_stages().get("test_generator", {})
            provider_id = st.get("provider", "ollama")
            model = st.get("model") or config.GEN_MODEL
        except Exception:
            pass
        provider = get_providers().get(provider_id) or get_providers().get("ollama")
        return await achat(
            provider, model,
            [{"role": "user", "content": prompt}],
            max_tokens=2000, temperature=0.3, timeout=float(config.REQUEST_TIMEOUT),
        )
    except Exception as e:
        logger.error(f"Test generation error: {e}")

    return ""


async def generate_tests_for_project(
    project_path: Path,
    function_name: Optional[str] = None,
    output_dir: Optional[Path] = None,
    progress=None,
) -> Dict:
    """Generate tests for all functions in a project.

    ``output_dir`` (optional) places the tests directly in a caller-chosen
    directory (e.g. ``outputs/<run>/03_mut``); otherwise a timestamped dir is
    created under ``config.OUTPUT_DIR``.
    """

    logger.info(f"Analyzing project: {project_path}")

    # Ensure path is absolute if needed
    if not project_path.is_absolute():
        project_path = Path.cwd() / project_path

    logger.info(f"Resolved path: {project_path}")
    logger.info(f"Path exists: {project_path.exists()}")

    if not project_path.exists():
        raise ValueError(f"Project path does not exist: {project_path}")

    functions = analyze_c_project(project_path)

    logger.info(f"Found {len(functions)} functions")

    if not functions:
        c_files = list(project_path.rglob("*.c")) + list(project_path.rglob("*.h"))
        logger.warning(f"No functions extracted. C/H files found: {[f.name for f in c_files]}")
        raise ValueError(
            f"No functions found in project. Found {len(c_files)} C/H files "
            f"but couldn't extract functions."
        )

    # Filter by function name if specified
    if function_name:
        functions = [f for f in functions if f.name == function_name]
        if not functions:
            raise ValueError(f"Function '{function_name}' not found")

    logger.info(f"Generating tests for {len(functions)} functions...")

    # Create output directory
    if output_dir is not None:
        output_dir = Path(output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = config.OUTPUT_DIR / f"tests_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_tests = []
    failed_functions = []

    for i, func in enumerate(functions, 1):
        logger.info(f"[{i}/{len(functions)}] Generating test for: {func.name}")
        if progress:
            try:
                progress(i - 1, len(functions), func.name)
            except Exception:
                pass

        try:
            # Retrieve similar examples
            examples = await retrieve_similar_examples(func, k=config.TOP_K)

            # Generate test
            test_code = await generate_cpputest(func, examples)

            if test_code:
                # Strip markdown code fences if present
                test_code = test_code.strip()
                # Remove opening fence: ```cpp, ```c, ```
                if test_code.startswith('```'):
                    lines = test_code.split('\n')
                    if lines[0].startswith('```'):
                        lines = lines[1:]  # Remove first line
                    test_code = '\n'.join(lines)
                # Remove closing fence: ```
                if test_code.endswith('```'):
                    lines = test_code.split('\n')
                    if lines[-1].strip() == '```':
                        lines = lines[:-1]  # Remove last line
                    test_code = '\n'.join(lines)
                test_code = test_code.strip()

                # Enforce a unique TEST_GROUP name so multiple generated files link.
                test_code = _uniquify_test_group(test_code, func.name)

                # Save test file
                test_file = output_dir / f"Test_{func.name}.cpp"

                # Build function signature for extern "C" declaration
                params_str = ', '.join([f"{p['type']} {p['name']}" for p in func.parameters])
                func_signature = f"{func.return_type} {func.name}({params_str})"

                with open(test_file, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(f"// Auto-generated CppUTest for function: {func.name}\n")
                    f.write(f"// Source: {func.file_path}:{func.line_number}\n")
                    f.write(f"// Generated: {datetime.now().isoformat()}\n\n")
                    f.write("#include \"CppUTest/TestHarness.h\"\n")
                    # AUTOSAR Std_Types (uint8/.../Std_ReturnType) come from the
                    # Rte_Type.h that mudmut_core.compilable generates next to the
                    # skeleton. Plain C projects have no such header, so include
                    # it only when it exists.
                    if (Path(func.file_path).parent / "Rte_Type.h").is_file():
                        f.write("#include \"Rte_Type.h\"\n")
                    # The module's own header (e.g. <SWC>.h from compilable) gives
                    # tests the runnable prototypes, design variables and constants.
                    module_header = Path(func.file_path).with_suffix(".h")
                    if module_header.is_file():
                        f.write(f"#include \"{module_header.name}\"\n")
                    f.write("\n")
                    f.write("// Function under test\n")
                    f.write("extern \"C\" {\n")
                    f.write(f"    {func_signature};\n")
                    f.write("}\n\n")
                    f.write(test_code)

                # Copy source C file and corresponding header to test directory
                try:
                    from shutil import copy2
                    source_file = Path(func.file_path)
                    if source_file.exists():
                        # Copy the C source file
                        dest_file = output_dir / source_file.name
                        copy2(source_file, dest_file)
                        logger.info(f"  Copied source: {source_file.name}")

                        # Also copy the corresponding header file if it exists
                        header_file = source_file.with_suffix('.h')
                        if header_file.exists():
                            dest_header = output_dir / header_file.name
                            copy2(header_file, dest_header)
                            logger.info(f"  Copied header: {header_file.name}")
                except Exception as e:
                    logger.warning(f"  Could not copy source/header files: {e}")

                generated_tests.append(str(test_file))
                logger.info(f"  Test saved: {test_file.name}")
            else:
                failed_functions.append(func.name)
                logger.warning(f"  Failed to generate test for {func.name}")

        except Exception as e:
            failed_functions.append(func.name)
            logger.error(f"  Error generating test for {func.name}: {e}")

    # Create main runner and Makefile
    create_main_runner(output_dir)
    create_makefile(output_dir)

    return {
        "functions_analyzed": len(functions),
        "tests_generated": len(generated_tests),
        "output_directory": str(output_dir),
        "failed_functions": failed_functions
    }


def create_main_runner(output_dir: Path):
    """Create main runner file for CppUTest"""
    main_runner_content = """// Auto-generated main runner for CppUTest
#include "CppUTest/CommandLineTestRunner.h"

int main(int argc, char** argv)
{
    return CommandLineTestRunner::RunAllTests(argc, argv);
}
"""

    runner_path = output_dir / "AllTests.cpp"
    with open(runner_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(main_runner_content)

    logger.info(f"Created main runner: {runner_path}")


def _uniquify_test_group(test_code: str, func_name: str) -> str:
    """Ensure each generated test file declares a unique TEST_GROUP name.

    Multiple ``Test_*.cpp`` files are linked into a single binary; if the LLM
    emits the same ``TEST_GROUP(Foo)`` name for several functions, the linker
    fails with duplicate-symbol errors.  Rename the original group name (in both
    ``TEST_GROUP(...)`` and ``TEST(<group>, ...)`` macros) to a unique,
    function-derived name.
    """
    import re
    if not test_code:
        return test_code
    groups = list(dict.fromkeys(
        re.findall(r"\bTEST_GROUP(?:_BASE)?\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)", test_code)
    ))
    safe = re.sub(r"[^A-Za-z0-9_]", "_", func_name)
    for i, original in enumerate(groups):
        group_name = f"{safe}_Group" if i == 0 else f"{safe}_Group{i + 1}"
        if original == group_name:
            continue
        # Rewrite only the group argument of the CppUTest macros. The group is
        # often named after the function under test, so a blanket rename would
        # also rewrite the calls to that function and break the build.
        test_code = re.sub(
            r"\b(TEST_GROUP_BASE|TEST_GROUP|IGNORE_TEST|TEST)(\s*\(\s*)"
            + re.escape(original) + r"\b",
            lambda m: m.group(1) + m.group(2) + group_name,
            test_code,
        )
        logger.info(f"  Assigned unique TEST_GROUP({group_name}) for {func_name}")
    return test_code


def create_makefile(output_dir: Path, cpputest: Optional[dict] = None, extra_cflags: str = ""):
    """Create Makefile for building generated tests with coverage support.

    ``cpputest`` (optional) carries the resolved install: ``home``, ``include_dir``,
    ``lib_dir``, ``has_ext`` (see ``mudmut_core.toolchain.find_cpputest``); those
    paths are baked in so the run folder builds against that exact CppUTest. Without
    it the Makefile targets an apt install (``CPPUTEST_HOME ?= /usr``). Records the
    real test exit code, generates lcov 2.x coverage, and re-raises the test exit
    code so CI / the native runner see genuine failures.
    """
    tab = "\t"
    cpputest = cpputest or {}
    home = cpputest.get("home") or "/usr"
    inc = cpputest.get("include_dir") or "$(CPPUTEST_HOME)/include"
    lib = cpputest.get("lib_dir") or "$(CPPUTEST_HOME)/lib"
    ext = " -lCppUTestExt" if cpputest.get("has_ext", True) else ""
    L = [
        "# Auto-generated Makefile for CppUTest with Coverage",
        f"# CppUTest: {home} (include {inc}, lib {lib})",
        "",
        "# CppUTest location (resolved when generated); override on the make command line.",
        f"CPPUTEST_HOME ?= {home}",
        f"CPPUTEST_INC ?= {inc}",
        f"CPPUTEST_LIB ?= {lib}",
        "",
        "# Compiler flags with coverage enabled; -MMD -MP track header dependencies",
        "CXXFLAGS += -Wall -Wextra -g -std=c++11 --coverage -fprofile-arcs -ftest-coverage -MMD -MP -I.",
        "CXXFLAGS += -I$(CPPUTEST_INC)",
        "CFLAGS += -Wall -Wextra -g -std=c99 --coverage -fprofile-arcs -ftest-coverage -MMD -MP -I.",
        "CFLAGS += -I$(CPPUTEST_INC)",
        f"LDFLAGS += -L$(CPPUTEST_LIB) -Wl,-rpath,$(CPPUTEST_LIB) -lCppUTest{ext} -lm --coverage",
    ] + ([f"CXXFLAGS += {extra_cflags}", f"CFLAGS += {extra_cflags}"] if extra_cflags.strip() else []) + [
        "",
        "# Source files",
        "TEST_SRC = $(wildcard Test_*.cpp) AllTests.cpp",
        "C_SRC = $(wildcard *.c)",
        "TEST_OBJS = $(TEST_SRC:.cpp=.o)",
        "C_OBJS = $(C_SRC:.c=.o)",
        "ALL_OBJS = $(TEST_OBJS) $(C_OBJS)",
        "DEPS = $(ALL_OBJS:.o=.d)",
        "TEST_TARGET = run_tests",
        "",
        "# Coverage files",
        "GCOV_FILES = $(wildcard *.gcda *.gcno *.gcov)",
        "COVERAGE_INFO = coverage.info",
        "COVERAGE_HTML_DIR = coverage_html",
        "",
        "# lcov 2.x compatibility flags",
        "LCOV_OPTS = --rc branch_coverage=1 --ignore-errors unused,inconsistent",
        "",
        "all: $(TEST_TARGET)",
        "",
        "$(TEST_TARGET): $(ALL_OBJS)",
        tab + "$(CXX) -o $@ $^ $(LDFLAGS)",
        "",
        "%.o: %.cpp",
        tab + "$(CXX) $(CXXFLAGS) -c $< -o $@",
        "",
        "%.o: %.c",
        tab + "$(CC) $(CFLAGS) -c $< -o $@",
        "",
        "-include $(DEPS)",
        "",
        "# Run tests with JUnit XML output; record the real exit code (re-raised by coverage).",
        "test: $(TEST_TARGET)",
        tab + "@rm -f cpputest_cpputest_*.xml",
        tab + "-./$(TEST_TARGET) -ojunit -k cpputest; echo $$? > .test_exit_code",
        tab + '@echo "<?xml version=\\"1.0\\" encoding=\\"UTF-8\\"?><testsuites>" > test-results.xml',
        tab + '@for f in cpputest_cpputest_*.xml; do \\',
        tab + tab + 'if [ -f "$$f" ]; then \\',
        tab + tab + tab + "sed -n '/<testsuite/,/<\\/testsuite>/p' \"$$f\" >> test-results.xml; \\",
        tab + tab + "fi; \\",
        tab + "done",
        tab + '@echo "</testsuites>" >> test-results.xml',
        tab + '@echo "JUnit XML files merged into test-results.xml"',
        "",
        "# Generate coverage reports and re-raise the real test exit code.",
        "coverage: test",
        tab + '@echo "Generating coverage reports..."',
        tab + '-lcov --capture --directory . --output-file $(COVERAGE_INFO) $(LCOV_OPTS) 2>&1 | grep -v "ignoring data for external file" || true',
        # Coverage of the code under test only: test files, the runner and the Rte stubs
        # would otherwise inflate the numbers.
        tab + "-lcov --remove $(COVERAGE_INFO) '/usr/*' '*/CppUTest/*' '*/Test_*' '*/AllTests.cpp' '*/Rte_Stubs.c' --output-file $(COVERAGE_INFO) $(LCOV_OPTS) 2>&1 | grep -v \"ignoring data for external file\" || true",
        tab + '-genhtml $(COVERAGE_INFO) --output-directory $(COVERAGE_HTML_DIR) --branch-coverage --legend --title "CppUTest Coverage Report" 2>&1 | tail -5 || true',
        tab + '@if [ -f $(COVERAGE_INFO) ]; then echo "Coverage reports generated successfully"; fi',
        tab + '@echo "HTML coverage: $(COVERAGE_HTML_DIR)/index.html"',
        tab + '@echo "LCOV file: $(COVERAGE_INFO)"',
        tab + '@exit_code=$$(cat .test_exit_code 2>/dev/null || echo 0); \\',
        tab + tab + 'rm -f .test_exit_code; \\',
        tab + tab + 'if [ "$$exit_code" != "0" ]; then \\',
        tab + tab + tab + 'echo "ERROR: unit tests failed (exit code $$exit_code)"; \\',
        tab + tab + tab + 'exit $$exit_code; \\',
        tab + tab + "fi",
        "",
        "# Clean all build artifacts including coverage files",
        "clean:",
        tab + "rm -f $(ALL_OBJS) $(DEPS) $(TEST_TARGET) $(GCOV_FILES) $(COVERAGE_INFO) .test_exit_code",
        tab + "rm -rf $(COVERAGE_HTML_DIR)",
        tab + "rm -f test-results.xml cpputest_cpputest_*.xml",
        "",
        ".PHONY: all clean test coverage",
    ]

    makefile_path = output_dir / "Makefile"
    # LF endings: GNU make (native or in WSL) chokes on the CRLF that text
    # mode writes on Windows ("/usr\r", broken "\" continuations).
    with open(makefile_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write("\n".join(L) + "\n")

    logger.info(f"Created Makefile with coverage support: {makefile_path}")
    write_run_scripts(output_dir)


_RUN_SH = """#!/usr/bin/env bash
# Auto-generated: compile and run the CppUTest suite in this folder (with coverage).
#   ./build_and_run.sh            -> make clean all coverage
#   ./build_and_run.sh test       -> any make targets: all, test, coverage, clean
# Windows: double-click or run build_and_run.bat (it calls this script inside WSL).
cd "$(dirname "$0")" || exit 1
if [ "$#" -eq 0 ]; then set -- clean all coverage; fi
echo "== make $* in $(pwd)"
make "$@"
rc=$?
echo "== exit code: $rc"
[ -f test-results.xml ] && echo "JUnit XML : $(pwd)/test-results.xml"
[ -f coverage_html/index.html ] && echo "Coverage  : $(pwd)/coverage_html/index.html"
exit $rc
"""

_RUN_BAT = """@echo off
REM Auto-generated: compile and run the CppUTest suite in this folder via WSL.
REM   build_and_run.bat            -> make clean all coverage
REM   build_and_run.bat test       -> any make targets
wsl.exe --cd "%~dp0." -e bash ./build_and_run.sh %*
exit /b %ERRORLEVEL%
"""


def write_run_scripts(output_dir: Path) -> None:
    """Write ``build_and_run.sh`` (LF) and ``build_and_run.bat`` (CRLF) next to the Makefile.

    They let anyone re-compile and re-run the generated tests without the UI or an agent.
    """
    output_dir = Path(output_dir)
    with open(output_dir / "build_and_run.sh", "w", encoding="utf-8", newline="\n") as f:
        f.write(_RUN_SH)
    with open(output_dir / "build_and_run.bat", "w", encoding="utf-8", newline="\r\n") as f:
        f.write(_RUN_BAT)
    try:
        (output_dir / "build_and_run.sh").chmod(0o755)
    except OSError:
        pass
    logger.info(f"Created build_and_run.sh / .bat in {output_dir}")
