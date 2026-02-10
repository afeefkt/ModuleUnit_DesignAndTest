"""C code analysis — AST-based and regex-based function extraction"""

from pathlib import Path
from typing import List
import logging
import re

from app.models import FunctionInfo

logger = logging.getLogger(__name__)

# Keep pycparser support (optional)
try:
    from pycparser import c_ast
    PYCPARSER_AVAILABLE = True
except ImportError:
    PYCPARSER_AVAILABLE = False
    logger.warning("pycparser not available - install with: pip install pycparser")


if PYCPARSER_AVAILABLE:
    class CFunctionVisitor(c_ast.NodeVisitor):
        """AST visitor to extract function definitions"""

        def __init__(self):
            self.functions = []
            self.current_file = ""

        def visit_FuncDef(self, node):
            func_info = {
                'name': node.decl.name,
                'return_type': self._get_type(node.decl.type.type),
                'parameters': self._get_parameters(node.decl.type.args),
                'line_number': node.coord.line if node.coord else 0,
                'source_code': self._get_function_source(node)
            }
            self.functions.append(func_info)

        def _get_type(self, type_node):
            """Extract type information"""
            if isinstance(type_node, c_ast.TypeDecl):
                return self._get_type(type_node.type)
            elif isinstance(type_node, c_ast.IdentifierType):
                return ' '.join(type_node.names)
            elif isinstance(type_node, c_ast.PtrDecl):
                return self._get_type(type_node.type) + '*'
            return 'void'

        def _get_parameters(self, param_list):
            """Extract function parameters"""
            if not param_list:
                return []

            params = []
            for param in param_list.params if hasattr(param_list, 'params') else []:
                if isinstance(param, c_ast.Decl):
                    param_type = self._get_type(param.type)
                    param_name = param.name or 'unnamed'
                    params.append({'type': param_type, 'name': param_name})
            return params

        def _get_function_source(self, node):
            """Approximate function source code"""
            return f"// Function at line {node.coord.line if node.coord else 'unknown'}"


def analyze_c_file_simple(file_path: Path) -> List[FunctionInfo]:
    """Simple regex-based C function analyzer (primary method)"""
    functions = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Remove comments to avoid false matches
        content = re.sub(r'//.*?\n', '\n', content)
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # Function definition pattern
        pattern = r'([a-zA-Z_][a-zA-Z0-9_]*(?:\s*\*)*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*\{'

        matches = list(re.finditer(pattern, content))
        logger.debug(f"Found {len(matches)} potential functions in {file_path.name}")

        for match in matches:
            return_type = match.group(1).strip()
            func_name = match.group(2).strip()
            params_str = match.group(3).strip()

            # Skip control structures
            control_keywords = ['if', 'while', 'for', 'switch', 'do', 'else', 'return']
            if return_type in control_keywords or func_name in control_keywords:
                continue

            # Skip common macros (ALL_UPPERCASE names)
            if func_name.isupper():
                continue

            # Parse parameters
            parameters = []
            if params_str and params_str != 'void' and params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    if param and param != 'void':
                        parts = re.split(r'\s+', param)
                        if len(parts) >= 2:
                            param_name = parts[-1].strip('*')
                            param_type = ' '.join(parts[:-1])
                            parameters.append({
                                'type': param_type,
                                'name': param_name
                            })
                        elif len(parts) == 1:
                            parameters.append({
                                'type': parts[0],
                                'name': 'unnamed'
                            })

            # Get line number
            line_num = content[:match.start()].count('\n') + 1

            # Extract function body
            start = match.end()
            brace_count = 1
            end = start

            for i in range(start, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break

            source_code = content[match.start():end]

            # Calculate complexity score
            complexity = (
                source_code.count('if') +
                source_code.count('else') +
                source_code.count('for') +
                source_code.count('while') +
                source_code.count('switch') +
                source_code.count('case')
            )

            func_info = FunctionInfo(
                name=func_name,
                return_type=return_type,
                parameters=parameters,
                file_path=str(file_path),
                line_number=line_num,
                source_code=source_code[:1000],
                complexity_score=complexity
            )

            functions.append(func_info)
            logger.debug(f"  Extracted: {return_type} {func_name}(...) at line {line_num}")

    except Exception as e:
        logger.error(f"Error analyzing {file_path}: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return functions


def analyze_c_project(project_path: Path) -> List[FunctionInfo]:
    """Analyze all C files in a project"""
    all_functions = []

    c_files = list(project_path.rglob("*.c")) + list(project_path.rglob("*.h"))

    logger.info(f"Found {len(c_files)} C/H files in {project_path}")

    for c_file in c_files:
        logger.info(f"Analyzing: {c_file.name}")
        functions = analyze_c_file_simple(c_file)
        all_functions.extend(functions)
        logger.info(f"  Found {len(functions)} functions")

    return all_functions
