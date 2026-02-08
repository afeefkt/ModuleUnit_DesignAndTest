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


async def generate_cpputest(function_info: FunctionInfo, examples: List[Dict]) -> str:
    """Generate CppUTest case using CodeLlama"""

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
5. Include mock setup if the function has dependencies
6. Add comments explaining what each test validates
7. Follow the style and structure of the reference examples

Generate ONLY the test code, starting with TEST_GROUP and including all test cases.
Do not include explanations or markdown formatting - just the C++ test code."""

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.OLLAMA_URL}/generate",
                json={
                    "model": config.GEN_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_predict": 2000
                    }
                },
                timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("response", "")
    except Exception as e:
        logger.error(f"Test generation error: {e}")

    return ""


async def generate_tests_for_project(
    project_path: Path,
    function_name: Optional[str] = None
) -> Dict:
    """Generate tests for all functions in a project"""

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = config.OUTPUT_DIR / f"tests_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_tests = []
    failed_functions = []

    for i, func in enumerate(functions, 1):
        logger.info(f"[{i}/{len(functions)}] Generating test for: {func.name}")

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

                # Save test file
                test_file = output_dir / f"Test_{func.name}.cpp"

                # Build function signature for extern "C" declaration
                params_str = ', '.join([f"{p['type']} {p['name']}" for p in func.parameters])
                func_signature = f"{func.return_type} {func.name}({params_str})"

                with open(test_file, 'w') as f:
                    f.write(f"// Auto-generated CppUTest for function: {func.name}\n")
                    f.write(f"// Source: {func.file_path}:{func.line_number}\n")
                    f.write(f"// Generated: {datetime.now().isoformat()}\n\n")
                    f.write("#include \"CppUTest/TestHarness.h\"\n\n")
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
    with open(runner_path, 'w') as f:
        f.write(main_runner_content)

    logger.info(f"Created main runner: {runner_path}")


def create_makefile(output_dir: Path):
    """Create Makefile for building generated tests"""
    makefile_content = """# Auto-generated Makefile for CppUTest

CPPUTEST_HOME = /usr/local

# Compiler flags
CXXFLAGS += -Wall -Wextra -g -std=c++11
CXXFLAGS += -I$(CPPUTEST_HOME)/include
CFLAGS += -Wall -Wextra -g -std=c99
LDFLAGS += -L$(CPPUTEST_HOME)/lib -lCppUTest -lCppUTestExt

# Source files
TEST_SRC = $(wildcard Test_*.cpp) AllTests.cpp
C_SRC = $(wildcard *.c)
TEST_OBJS = $(TEST_SRC:.cpp=.o)
C_OBJS = $(C_SRC:.c=.o)
ALL_OBJS = $(TEST_OBJS) $(C_OBJS)
TEST_TARGET = run_tests

all: $(TEST_TARGET)

$(TEST_TARGET): $(ALL_OBJS)
\t$(CXX) -o $@ $^ $(LDFLAGS)

%.o: %.cpp
\t$(CXX) $(CXXFLAGS) -c $< -o $@

%.o: %.c
\t$(CC) $(CFLAGS) -c $< -o $@

clean:
\trm -f $(ALL_OBJS) $(TEST_TARGET)

test: $(TEST_TARGET)
\t./$(TEST_TARGET)

.PHONY: all clean test
"""

    makefile_path = output_dir / "Makefile"
    with open(makefile_path, 'w') as f:
        f.write(makefile_content)

    logger.info(f"Created Makefile: {makefile_path}")
