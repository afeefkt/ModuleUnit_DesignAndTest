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


# Comments and string/char literals, masked before matching so braces or
# keywords inside them can't confuse the scanner.
_MASK_RE = re.compile(
    r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'',
    re.DOTALL,
)

# Function definition: declaration specifiers + name + (params) + '{'.
# The specifier group allows pointer stars glued to the name (char *foo()).
_FUNC_DEF_RE = re.compile(
    r'^[ \t]*((?:[A-Za-z_]\w*[ \t\*]+|\*[ \t]*)+?)\**[ \t]*([A-Za-z_]\w*)\s*\(([^;{}()]*)\)\s*\{',
    re.MULTILINE,
)

_CONTROL_KEYWORDS = {'if', 'while', 'for', 'switch', 'do', 'else', 'return', 'case', 'sizeof'}
_STORAGE_SPECIFIERS = {'static', 'inline', '__inline', '__inline__', 'extern'}
_DECISION_RE = re.compile(r'\b(?:if|for|while|case)\b|&&|\|\|')

# Source kept per function for the LLM prompt (was 1000 chars, which cut
# most real functions in half).
MAX_SOURCE_CHARS = 4000


def _mask(content: str) -> str:
    """Blank out comments/literals, preserving length and newlines so match
    offsets and line numbers still refer to the original text."""
    return _MASK_RE.sub(lambda m: re.sub(r'[^\n]', ' ', m.group(0)), content)


def _normalize_type(text: str) -> str:
    """'const  char*' -> 'const char *', 'char**' -> 'char **'."""
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r'\s*(\*+)\s*', r' \1', text).strip()


def _parse_params(params_str: str) -> List[dict]:
    params_str = params_str.strip()
    if not params_str or params_str == 'void':
        return []
    params = []
    for raw in params_str.split(','):
        raw = raw.strip()
        if not raw or raw == 'void':
            continue
        if raw == '...':
            params.append({'type': '...', 'name': ''})
            continue
        m = re.match(r'^(.*?[\s\*])([A-Za-z_]\w*)\s*((?:\[[^\]]*\])*)$', raw)
        if m and m.group(1).strip():
            ptype = _normalize_type(m.group(1))
            if m.group(3):  # int buf[8] -> int * buf (decays to a pointer)
                ptype = _normalize_type(ptype + ' *')
            params.append({'type': ptype, 'name': m.group(2)})
        else:
            params.append({'type': _normalize_type(raw), 'name': 'unnamed'})
    return params


def analyze_c_file_simple(file_path: Path) -> List[FunctionInfo]:
    """Regex-based C function analyzer (primary method)."""
    functions = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        masked = _mask(content)
        matches = list(_FUNC_DEF_RE.finditer(masked))
        logger.debug(f"Found {len(matches)} potential functions in {file_path.name}")

        for match in matches:
            specifiers = match.group(1)
            func_name = match.group(2)
            words = re.findall(r'[A-Za-z_]\w*', specifiers)

            # Skip control structures and macros (ALL_UPPERCASE names)
            if func_name in _CONTROL_KEYWORDS or any(w in _CONTROL_KEYWORDS for w in words):
                continue
            if func_name.isupper():
                continue

            is_static = 'static' in words
            # specifiers + any '*' glued to the name, minus storage-class words
            type_text = masked[match.start(1):match.start(2)]
            type_text = re.sub(
                r'\b(?:' + '|'.join(_STORAGE_SPECIFIERS) + r')\b', ' ', type_text
            )
            return_type = _normalize_type(type_text) or 'int'

            # Find the matching closing brace in the masked text
            start = match.end()
            depth = 1
            end = len(masked)
            for i in range(start, len(masked)):
                if masked[i] == '{':
                    depth += 1
                elif masked[i] == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break

            # Original text (with comments — they carry /* [REQ-..] */ trace IDs)
            source_code = content[match.start():end].strip('\n')
            body = masked[start:end]

            func_info = FunctionInfo(
                name=func_name,
                return_type=return_type,
                parameters=_parse_params(match.group(3)),
                file_path=str(file_path),
                line_number=masked.count('\n', 0, match.start(2)) + 1,
                source_code=source_code[:MAX_SOURCE_CHARS],
                complexity_score=len(_DECISION_RE.findall(body)),
                is_static=is_static,
            )

            functions.append(func_info)
            logger.debug(f"  Extracted: {return_type} {func_name}(...) at line {func_info.line_number}")

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
