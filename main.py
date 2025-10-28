"""
CppUTest Generator with RAG - Automatic Test Case Generation for C Projects
Analyzes C code and generates CppUTest cases based on example templates
"""

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any, Tuple
import os
import faiss
import pickle
import numpy as np
import aiohttp
import asyncio
import re
from pathlib import Path
import logging
from datetime import datetime
import hashlib
import json
from functools import lru_cache
import time
import shutil
import zipfile
from io import BytesIO

# For C code parsing
try:
    from pycparser import c_parser, c_ast, parse_file
    PYCPARSER_AVAILABLE = True
except ImportError:
    PYCPARSER_AVAILABLE = False
    logging.warning("pycparser not available - install with: pip install pycparser")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cpputest_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
class Config(BaseModel):
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api")
    EMBED_MODEL: str = os.getenv("EMBED_MODEL", "all-minilm:latest")
    GEN_MODEL: str = os.getenv("GEN_MODEL", "codellama:latest")
    
    # Directories
    C_PROJECT_DIR: Path = Path(os.getenv("C_PROJECT_DIR", "./c_projects"))
    TEST_EXAMPLES_DIR: Path = Path(os.getenv("TEST_EXAMPLES_DIR", "./test_examples"))
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "./generated_tests"))
    
    # Chunk settings for large projects
    MAX_FUNCTIONS_PER_CHUNK: int = int(os.getenv("MAX_FUNCTIONS_PER_CHUNK", "10"))
    
    # Retrieval settings
    TOP_K: int = int(os.getenv("TOP_K", "3"))
    
    # Index files
    INDEX_FILE: str = "test_examples.index"
    META_FILE: str = "test_examples_meta.pkl"
    HASH_FILE: str = "examples_hash.json"
    
    # Performance settings
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "5"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "180"))
    
    @validator('C_PROJECT_DIR', 'TEST_EXAMPLES_DIR', 'OUTPUT_DIR')
    def ensure_dirs_exist(cls, v):
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {v}")
        return v

config = Config()

# Pydantic models
class FunctionInfo(BaseModel):
    name: str
    return_type: str
    parameters: List[Dict[str, str]]
    file_path: str
    line_number: int
    source_code: str
    complexity_score: int = 0

class GenerateTestRequest(BaseModel):
    project_path: Optional[str] = None
    function_name: Optional[str] = None
    generate_all: bool = False

class TestGenerationResponse(BaseModel):
    status: str
    functions_analyzed: int
    tests_generated: int
    output_directory: str
    failed_functions: List[str]
    elapsed_seconds: float

class ProjectAnalysisResponse(BaseModel):
    total_files: int
    total_functions: int
    functions: List[FunctionInfo]
    project_structure: Dict[str, Any]

# FastAPI setup
app = FastAPI(
    title="CppUTest Generator with RAG",
    description="Automatic test case generation for C projects using CodeLlama",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
index = None
test_examples_metadata = {"texts": [], "meta": [], "examples": {}}

# ========== C CODE ANALYSIS ==========

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
        # This is a simplified version - in production, you'd extract actual source
        return f"// Function at line {node.coord.line if node.coord else 'unknown'}"

def analyze_c_file_simple(file_path: Path) -> List[FunctionInfo]:
    """Simple regex-based C function analyzer (fallback)"""
    functions = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Remove comments to avoid false matches
        # Remove single-line comments
        content = re.sub(r'//.*?\n', '\n', content)
        # Remove multi-line comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Improved regex to find function definitions
        # Matches: return_type function_name(parameters) { ... }
        # Also handles pointers and multiple spaces
        pattern = r'([a-zA-Z_][a-zA-Z0-9_]*(?:\s*\*)*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*\{'
        
        matches = list(re.finditer(pattern, content))
        logger.debug(f"Found {len(matches)} potential functions in {file_path.name}")
        
        for match in matches:
            return_type = match.group(1).strip()
            func_name = match.group(2).strip()
            params_str = match.group(3).strip()
            
            # Skip if it looks like a control structure or macro
            control_keywords = ['if', 'while', 'for', 'switch', 'do', 'else', 'return']
            if return_type in control_keywords or func_name in control_keywords:
                continue
            
            # Skip common macros
            if func_name.isupper():  # Likely a macro
                continue
            
            # Parse parameters
            parameters = []
            if params_str and params_str != 'void' and params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    if param and param != 'void':
                        # Handle complex parameter types
                        parts = re.split(r'\s+', param)
                        if len(parts) >= 2:
                            param_name = parts[-1].strip('*')
                            param_type = ' '.join(parts[:-1])
                            parameters.append({
                                'type': param_type,
                                'name': param_name
                            })
                        elif len(parts) == 1:
                            # Just a type, no name
                            parameters.append({
                                'type': parts[0],
                                'name': 'unnamed'
                            })
            
            # Get line number
            line_num = content[:match.start()].count('\n') + 1
            
            # Extract function body (simplified)
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
            
            # Calculate complexity
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
                source_code=source_code[:1000],  # Limit to first 1000 chars
                complexity_score=complexity
            )
            
            functions.append(func_info)
            logger.debug(f"  Extracted: {return_type} {func_name}(...) at line {line_num}")
    
    except Exception as e:
        logger.error(f"Error analyzing {file_path}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return functions
    
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

# ========== EMBEDDING AND RAG ==========

async def embed_text(text: str, session: aiohttp.ClientSession) -> Optional[np.ndarray]:
    """Generate embedding for text"""
    if not text or not text.strip():
        return None
    
    try:
        url = f"{config.OLLAMA_URL}/embeddings"
        payload = {
            "model": config.EMBED_MODEL,
            "prompt": text
        }
        
        async with session.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
        ) as response:
            if response.status == 200:
                result = await response.json()
                embedding = result.get("embedding")
                if embedding:
                    return np.array(embedding, dtype="float32")
    except Exception as e:
        logger.error(f"Embedding error: {e}")
    
    return None

async def build_examples_index():
    """Build FAISS index from test example files"""
    global index, test_examples_metadata
    
    logger.info("Building index from test examples...")
    
    example_files = list(config.TEST_EXAMPLES_DIR.rglob("*.cpp")) + \
                   list(config.TEST_EXAMPLES_DIR.rglob("*.c"))
    
    if not example_files:
        logger.warning(f"No example files found in {config.TEST_EXAMPLES_DIR}")
        return
    
    texts = []
    metadata = []
    
    for example_file in example_files:
        try:
            with open(example_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            texts.append(content)
            metadata.append({
                'file': example_file.name,
                'path': str(example_file)
            })
            
            logger.info(f"Added example: {example_file.name}")
        except Exception as e:
            logger.error(f"Error reading {example_file}: {e}")
    
    if not texts:
        logger.warning("No text extracted from examples")
        return
    
    # Generate embeddings
    logger.info(f"Generating embeddings for {len(texts)} examples...")
    vectors = []
    
    async with aiohttp.ClientSession() as session:
        for i, text in enumerate(texts):
            vec = await embed_text(text, session)
            if vec is not None:
                vectors.append(vec)
            else:
                logger.warning(f"Failed to embed example {i}")
    
    if not vectors:
        logger.error("Failed to generate any embeddings")
        return
    
    # Create FAISS index
    dim = vectors[0].shape[0]
    vectors_array = np.vstack(vectors)
    faiss.normalize_L2(vectors_array)
    
    index = faiss.IndexFlatIP(dim)
    index.add(vectors_array)
    
    # Save
    faiss.write_index(index, config.INDEX_FILE)
    
    test_examples_metadata = {
        "texts": texts,
        "meta": metadata,
        "created_at": datetime.now().isoformat()
    }
    
    with open(config.META_FILE, "wb") as f:
        pickle.dump(test_examples_metadata, f)
    
    logger.info(f"Index built: {len(vectors)} examples indexed")

async def retrieve_similar_examples(function_info: FunctionInfo, k: int = 3) -> List[Dict]:
    """Retrieve similar test examples"""
    if index is None:
        return []
    
    # Create query from function info
    query = f"""
    Function: {function_info.name}
    Return type: {function_info.return_type}
    Parameters: {', '.join([f"{p['type']} {p['name']}" for p in function_info.parameters])}
    Source:
    {function_info.source_code[:500]}
    """
    
    async with aiohttp.ClientSession() as session:
        qvec = await embed_text(query, session)
    
    if qvec is None:
        return []
    
    qvec = qvec.reshape(1, -1)
    faiss.normalize_L2(qvec)
    
    k = min(k, len(test_examples_metadata["texts"]))
    distances, indices = index.search(qvec, k)
    
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < len(test_examples_metadata["texts"]):
            results.append({
                "text": test_examples_metadata["texts"][idx],
                "metadata": test_examples_metadata["meta"][idx],
                "score": float(dist)
            })
    
    return results

# ========== TEST GENERATION ==========

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

async def generate_tests_for_project(project_path: Path, function_name: Optional[str] = None):
    """Generate tests for all functions in project"""
    
    # Analyze project
    logger.info(f"Analyzing project: {project_path}")
    
    # Ensure path is absolute if it starts with /app
    if not project_path.is_absolute():
        project_path = Path.cwd() / project_path
    
    logger.info(f"Resolved path: {project_path}")
    logger.info(f"Path exists: {project_path.exists()}")
    
    if not project_path.exists():
        raise ValueError(f"Project path does not exist: {project_path}")
    
    functions = analyze_c_project(project_path)
    
    logger.info(f"Found {len(functions)} functions")
    
    if not functions:
        # List what files were found
        c_files = list(project_path.rglob("*.c")) + list(project_path.rglob("*.h"))
        logger.warning(f"No functions extracted. C/H files found: {[f.name for f in c_files]}")
        raise ValueError(f"No functions found in project. Found {len(c_files)} C/H files but couldn't extract functions.")
    
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
                # Save test file
                test_file = output_dir / f"Test_{func.name}.cpp"
                with open(test_file, 'w') as f:
                    f.write(f"// Auto-generated CppUTest for function: {func.name}\n")
                    f.write(f"// Source: {func.file_path}:{func.line_number}\n")
                    f.write(f"// Generated: {datetime.now().isoformat()}\n\n")
                    f.write("#include \"CppUTest/TestHarness.h\"\n\n")
                    f.write(test_code)
                
                generated_tests.append(str(test_file))
                logger.info(f"  ✓ Test saved: {test_file.name}")
            else:
                failed_functions.append(func.name)
                logger.warning(f"  ✗ Failed to generate test for {func.name}")
                
        except Exception as e:
            failed_functions.append(func.name)
            logger.error(f"  ✗ Error generating test for {func.name}: {e}")
    
    # Create Makefile
    create_makefile(output_dir, generated_tests)
    
    return {
        "functions_analyzed": len(functions),
        "tests_generated": len(generated_tests),
        "output_directory": str(output_dir),
        "failed_functions": failed_functions
    }

def create_makefile(output_dir: Path, test_files: List[str]):
    """Create Makefile for building tests"""
    makefile_content = """# Auto-generated Makefile for CppUTest

CPPUTEST_HOME = /usr/local

CXXFLAGS += -Wall -Wextra -g -std=c++11
CXXFLAGS += -I$(CPPUTEST_HOME)/include
LDFLAGS += -L$(CPPUTEST_HOME)/lib -lCppUTest -lCppUTestExt

TEST_SRC = $(wildcard Test_*.cpp)
TEST_OBJS = $(TEST_SRC:.cpp=.o)
TEST_TARGET = run_tests

all: $(TEST_TARGET)

$(TEST_TARGET): $(TEST_OBJS)
\t$(CXX) -o $@ $^ $(LDFLAGS)

%.o: %.cpp
\t$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
\trm -f $(TEST_OBJS) $(TEST_TARGET)

test: $(TEST_TARGET)
\t./$(TEST_TARGET)

.PHONY: all clean test
"""
    
    makefile_path = output_dir / "Makefile"
    with open(makefile_path, 'w') as f:
        f.write(makefile_content)
    
    logger.info(f"Created Makefile: {makefile_path}")

# ========== API ROUTES ==========

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Starting CppUTest Generator...")
    logger.info(f"Ollama URL: {config.OLLAMA_URL}")
    logger.info(f"Code Model: {config.GEN_MODEL}")
    
    # Create example CppUTest file if examples directory is empty
    create_example_cpputest_files()
    
    # Build index from examples
    await build_examples_index()

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "ollama_url": config.OLLAMA_URL,
        "model": config.GEN_MODEL,
        "index_loaded": index is not None,
        "examples_count": len(test_examples_metadata.get("texts", []))
    }

@app.get("/debug/list-projects")
async def list_projects():
    """Debug endpoint to list available projects"""
    projects = []
    
    logger.info(f"Listing projects in: {config.C_PROJECT_DIR}")
    
    if config.C_PROJECT_DIR.exists():
        for item in config.C_PROJECT_DIR.iterdir():
            if item.is_dir():
                c_files = list(item.rglob("*.c")) + list(item.rglob("*.h"))
                projects.append({
                    "name": item.name,
                    "path": str(item),
                    "c_files_count": len(c_files),
                    "files": [f.name for f in c_files[:10]]  # First 10 files
                })
    
    return {
        "c_project_dir": str(config.C_PROJECT_DIR),
        "c_project_dir_absolute": str(config.C_PROJECT_DIR.absolute()),
        "exists": config.C_PROJECT_DIR.exists(),
        "projects": projects,
        "cwd": str(Path.cwd())
    }

@app.get("/debug/test-parse")
async def test_parse(file_path: str = Query(...)):
    """Debug endpoint to test parsing a specific file"""
    path = Path(file_path)
    
    logger.info(f"Testing parse for: {file_path}")
    logger.info(f"Resolved to: {path}")
    logger.info(f"Exists: {path.exists()}")
    
    if not path.exists():
        return {
            "error": "File not found", 
            "path": str(path),
            "absolute": str(path.absolute()),
            "cwd": str(Path.cwd())
        }
    
    try:
        functions = analyze_c_file_simple(path)
        
        # Also show raw content sample
        with open(path, 'r', errors='ignore') as f:
            content = f.read()
        
        return {
            "file": str(path),
            "functions_found": len(functions),
            "functions": [
                {
                    "name": f.name,
                    "return_type": f.return_type,
                    "params": f.parameters,
                    "line": f.line_number
                }
                for f in functions
            ],
            "file_size": len(content),
            "first_500_chars": content[:500],
            "line_count": content.count('\n')
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/analyze-project", response_model=ProjectAnalysisResponse)
async def analyze_project_endpoint(project_path: str = Query(...)):
    """Analyze a C project"""
    path = Path(project_path)
    
    logger.info(f"Analyzing project: {project_path}")
    logger.info(f"Resolved to: {path}")
    logger.info(f"Absolute path: {path.absolute()}")
    logger.info(f"Exists: {path.exists()}")
    
    if not path.exists():
        # Try to find it relative to C_PROJECT_DIR
        alt_path = config.C_PROJECT_DIR / Path(project_path).name
        if alt_path.exists():
            path = alt_path
            logger.info(f"Using alternative path: {path}")
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Project path not found: {path}. Also tried: {alt_path}"
            )
    
    functions = analyze_c_project(path)
    
    logger.info(f"Analysis complete: found {len(functions)} functions")
    
    # Build project structure
    c_files = list(path.rglob("*.c")) + list(path.rglob("*.h"))
    
    total_lines = 0
    for f in c_files:
        try:
            with open(f, 'r', errors='ignore') as file:
                total_lines += len(file.readlines())
        except:
            pass
    
    structure = {
        "files": [str(f.relative_to(path)) for f in c_files],
        "total_lines": total_lines
    }
    
    return ProjectAnalysisResponse(
        total_files=len(c_files),
        total_functions=len(functions),
        functions=functions,
        project_structure=structure
    )

@app.post("/generate-tests", response_model=TestGenerationResponse)
async def generate_tests_endpoint(request: GenerateTestRequest):
    """Generate CppUTest cases"""
    start_time = time.time()
    
    if not request.project_path:
        raise HTTPException(status_code=400, detail="project_path is required")
    
    # Handle the path properly - convert relative to absolute if needed
    project_path_str = request.project_path
    
    # Remove leading/trailing whitespace
    project_path_str = project_path_str.strip()
    
    # If path starts with /app, use it as is, otherwise treat as relative
    if project_path_str.startswith('/app/'):
        project_path = Path(project_path_str)
    elif project_path_str.startswith('./'):
        project_path = Path(project_path_str)
    else:
        # Assume it's relative to current working directory
        project_path = Path(project_path_str)
    
    logger.info(f"Request path: {request.project_path}")
    logger.info(f"Resolved path: {project_path}")
    logger.info(f"Absolute path: {project_path.absolute()}")
    logger.info(f"Path exists: {project_path.exists()}")
    
    if not project_path.exists():
        # Try alternative paths
        alt_path = config.C_PROJECT_DIR / project_path.name
        if alt_path.exists():
            project_path = alt_path
            logger.info(f"Using alternative path: {project_path}")
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"Project path not found: {project_path}. Also tried: {alt_path}"
            )
    
    try:
        result = await generate_tests_for_project(
            project_path,
            function_name=request.function_name
        )
        
        elapsed = time.time() - start_time
        
        return TestGenerationResponse(
            status="success",
            elapsed_seconds=elapsed,
            **result
        )
    except Exception as e:
        logger.error(f"Test generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rebuild-examples-index")
async def rebuild_examples_index():
    """Rebuild the examples index"""
    try:
        await build_examples_index()
        return {"status": "success", "examples_indexed": len(test_examples_metadata.get("texts", []))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== EXAMPLE CREATION ==========

def create_example_cpputest_files():
    """Create example CppUTest files"""
    examples_dir = config.TEST_EXAMPLES_DIR
    
    example1 = examples_dir / "example_simple_function.cpp"
    if not example1.exists():
        with open(example1, 'w') as f:
            f.write("""// Example CppUTest for a simple function
#include "CppUTest/TestHarness.h"

// Function under test
int add(int a, int b) {
    return a + b;
}

TEST_GROUP(AddFunctionTests)
{
    void setup() {
        // Setup before each test
    }
    
    void teardown() {
        // Cleanup after each test
    }
};

TEST(AddFunctionTests, AddPositiveNumbers)
{
    // Test adding two positive numbers
    int result = add(5, 3);
    CHECK_EQUAL(8, result);
}

TEST(AddFunctionTests, AddNegativeNumbers)
{
    // Test adding two negative numbers
    int result = add(-5, -3);
    CHECK_EQUAL(-8, result);
}

TEST(AddFunctionTests, AddZero)
{
    // Test adding zero
    int result = add(0, 5);
    CHECK_EQUAL(5, result);
}

TEST(AddFunctionTests, AddMixedSignNumbers)
{
    // Test adding positive and negative
    int result = add(10, -5);
    CHECK_EQUAL(5, result);
}
""")
        logger.info(f"Created example: {example1}")
    
    example2 = examples_dir / "example_string_function.cpp"
    if not example2.exists():
        with open(example2, 'w') as f:
            f.write("""// Example CppUTest for string manipulation
#include "CppUTest/TestHarness.h"
#include <string.h>

// Function under test
char* string_reverse(char* str) {
    if (!str) return NULL;
    int len = strlen(str);
    for (int i = 0; i < len/2; i++) {
        char temp = str[i];
        str[i] = str[len-1-i];
        str[len-1-i] = temp;
    }
    return str;
}

TEST_GROUP(StringReverse)
{
    char buffer[100];
    
    void setup() {
        memset(buffer, 0, sizeof(buffer));
    }
    
    void teardown() {
    }
};

TEST(StringReverse, ReverseNormalString)
{
    strcpy(buffer, "hello");
    string_reverse(buffer);
    STRCMP_EQUAL("olleh", buffer);
}

TEST(StringReverse, ReverseSingleCharacter)
{
    strcpy(buffer, "a");
    string_reverse(buffer);
    STRCMP_EQUAL("a", buffer);
}

TEST(StringReverse, ReverseEmptyString)
{
    strcpy(buffer, "");
    string_reverse(buffer);
    STRCMP_EQUAL("", buffer);
}

TEST(StringReverse, ReverseNullPointer)
{
    char* result = string_reverse(NULL);
    CHECK(result == NULL);
}
""")
        logger.info(f"Created example: {example2}")

# ========== WEB UI ==========

@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve web interface"""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>CppUTest Generator</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            .header h1 { font-size: 2em; margin-bottom: 10px; }
            .content { padding: 30px; }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 8px;
            }
            .section h2 {
                margin-bottom: 15px;
                color: #495057;
            }
            input, textarea {
                width: 100%;
                padding: 12px;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                font-size: 1em;
                margin-bottom: 10px;
            }
            button {
                padding: 12px 24px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 1em;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s;
            }
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }
            .result {
                margin-top: 20px;
                padding: 15px;
                background: white;
                border-radius: 8px;
                display: none;
            }
            .result.show { display: block; }
            .loading {
                text-align: center;
                padding: 20px;
                display: none;
            }
            .loading.show { display: block; }
            .spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .function-list {
                max-height: 400px;
                overflow-y: auto;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 10px;
            }
            .function-item {
                padding: 10px;
                margin: 5px 0;
                background: white;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                cursor: pointer;
            }
            .function-item:hover {
                background: #f8f9fa;
                border-color: #667eea;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🧪 CppUTest Generator</h1>
                <p>Automatic Test Generation for C Projects using CodeLlama</p>
            </div>
            
            <div class="content">
                <div class="section">
                    <h2>📁 Analyze Project</h2>
                    <input type="text" id="analyze-path" placeholder="Enter project path (e.g., ./c_projects/my_project)" />
                    <button onclick="analyzeProject()">Analyze Project</button>
                    
                    <div class="loading" id="analyze-loading">
                        <div class="spinner"></div>
                        <p>Analyzing project...</p>
                    </div>
                    
                    <div class="result" id="analyze-result"></div>
                </div>
                
                <div class="section">
                    <h2>🔧 Generate Tests</h2>
                    <input type="text" id="generate-path" placeholder="Project path" />
                    <input type="text" id="function-name" placeholder="Function name (optional - leave empty for all)" />
                    <button onclick="generateTests()">Generate CppUTest Cases</button>
                    
                    <div class="loading" id="generate-loading">
                        <div class="spinner"></div>
                        <p>Generating tests... This may take a while...</p>
                    </div>
                    
                    <div class="result" id="generate-result"></div>
                </div>
                
                <div class="section">
                    <h2>📚 Test Examples</h2>
                    <p>Upload example CppUTest files to improve generation quality</p>
                    <button onclick="rebuildIndex()">Rebuild Examples Index</button>
                    
                    <div class="result" id="index-result"></div>
                </div>
            </div>
        </div>

        <script>
            let lastAnalyzedPath = '';
            let analyzedFunctions = [];
            
            async function analyzeProject() {
                const path = document.getElementById('analyze-path').value.trim();
                if (!path) {
                    alert('Please enter a project path');
                    return;
                }
                
                lastAnalyzedPath = path;
                document.getElementById('analyze-loading').classList.add('show');
                document.getElementById('analyze-result').classList.remove('show');
                
                try {
                    const res = await fetch(`/analyze-project?project_path=${encodeURIComponent(path)}`);
                    if (!res.ok) {
                        const error = await res.json();
                        throw new Error(error.detail || 'Analysis failed');
                    }
                    
                    const data = await res.json();
                    analyzedFunctions = data.functions;
                    
                    // IMPORTANT: Auto-fill the generate path with the SAME path used for analysis
                    document.getElementById('generate-path').value = path;
                    console.log('Auto-filled generate path:', path);
                    
                    let html = `
                        <h3>✅ Analysis Complete</h3>
                        <p><strong>Files:</strong> ${data.total_files}</p>
                        <p><strong>Functions Found:</strong> ${data.total_functions}</p>
                        <p><strong>Total Lines:</strong> ${data.project_structure.total_lines}</p>
                        <h4>Files in project:</h4>
                        <div style="max-height: 150px; overflow-y: auto; background: white; padding: 10px; border-radius: 4px; margin-bottom: 15px;">
                            ${data.project_structure.files.map(f => `<div>📄 ${f}</div>`).join('')}
                        </div>
                        <h4>Functions detected:</h4>
                        <div class="function-list">
                    `;
                    
                    if (data.functions.length === 0) {
                        html += '<p style="color: #dc3545;">⚠️ No functions found. Check if files contain valid C function definitions.</p>';
                    } else {
                        data.functions.forEach(func => {
                            const params = func.parameters.map(p => `${p.type} ${p.name}`).join(', ');
                            html += `
                                <div class="function-item">
                                    <strong>${func.return_type} ${func.name}(${params || 'void'})</strong><br>
                                    <small>📁 ${func.file_path.split('/').pop()} | Line: ${func.line_number} | Complexity: ${func.complexity_score}</small>
                                </div>
                            `;
                        });
                    }
                    
                    html += '</div>';
                    
                    document.getElementById('analyze-result').innerHTML = html;
                    document.getElementById('analyze-result').classList.add('show');
                    
                } catch (err) {
                    alert('Error: ' + err.message);
                    console.error(err);
                } finally {
                    document.getElementById('analyze-loading').classList.remove('show');
                }
            }
            
            async function generateTests() {
                const path = document.getElementById('generate-path').value.trim();
                const funcName = document.getElementById('function-name').value.trim();
                
                if (!path) {
                    alert('Please enter a project path (or analyze first)');
                    return;
                }
                
                // Use the last analyzed path if generate-path is empty
                const projectPath = path || lastAnalyzedPath;
                
                if (!projectPath) {
                    alert('Please analyze a project first or enter a project path');
                    return;
                }
                
                console.log('Generating tests for path:', projectPath);
                
                if (!confirm(`Generate CppUTest cases for ${funcName || 'ALL functions'}?\n\nProject: ${projectPath}\n\nThis may take several minutes...`)) {
                    return;
                }
                
                document.getElementById('generate-loading').classList.add('show');
                document.getElementById('generate-result').classList.remove('show');
                
                try {
                    const res = await fetch('/generate-tests', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            project_path: projectPath,
                            function_name: funcName || null,
                            generate_all: !funcName
                        })
                    });
                    
                    console.log('Response status:', res.status);
                    
                    if (!res.ok) {
                        const error = await res.json();
                        console.error('Error response:', error);
                        throw new Error(error.detail || 'Generation failed');
                    }
                    
                    const data = await res.json();
                    
                    let html = `
                        <h3>✅ Generation Complete!</h3>
                        <p><strong>Functions Analyzed:</strong> ${data.functions_analyzed}</p>
                        <p><strong>Tests Generated:</strong> ${data.tests_generated}</p>
                        <p><strong>Output Directory:</strong> <code>${data.output_directory}</code></p>
                        <p><strong>Time Elapsed:</strong> ${data.elapsed_seconds.toFixed(2)}s</p>
                    `;
                    
                    if (data.failed_functions.length > 0) {
                        html += `
                            <h4>⚠️ Failed Functions (${data.failed_functions.length}):</h4>
                            <ul>
                                ${data.failed_functions.map(f => `<li>${f}</li>`).join('')}
                            </ul>
                        `;
                    }
                    
                    html += `
                        <h4>📋 Next Steps:</h4>
                        <ol>
                            <li>Review generated tests in: <code>${data.output_directory}</code></li>
                            <li>Build tests: <code>cd ${data.output_directory} && make</code></li>
                            <li>Run tests: <code>./run_tests</code></li>
                        </ol>
                    `;
                    
                    document.getElementById('generate-result').innerHTML = html;
                    document.getElementById('generate-result').classList.add('show');
                    
                } catch (err) {
                    alert('Error: ' + err.message);
                    console.error(err);
                } finally {
                    document.getElementById('generate-loading').classList.remove('show');
                }
            }
            
            async function rebuildIndex() {
                try {
                    const res = await fetch('/rebuild-examples-index', { method: 'POST' });
                    if (!res.ok) throw new Error(await res.text());
                    
                    const data = await res.json();
                    
                    document.getElementById('index-result').innerHTML = `
                        <p>✅ Index rebuilt successfully</p>
                        <p><strong>Examples Indexed:</strong> ${data.examples_indexed}</p>
                    `;
                    document.getElementById('index-result').classList.add('show');
                    
                } catch (err) {
                    alert('Error: ' + err.message);
                }
            }
            
            async function listProjects() {
                try {
                    const res = await fetch('/debug/list-projects');
                    const data = await res.json();
                    
                    console.log('Available projects:', data);
                    alert(`Found ${data.projects.length} projects. Check console for details.`);
                } catch (err) {
                    console.error(err);
                }
            }
        </script>
    </body>
    </html>
    """)

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting CppUTest Generator on {host}:{port}")
    logger.info(f"Project directory: {config.C_PROJECT_DIR}")
    logger.info(f"Examples directory: {config.TEST_EXAMPLES_DIR}")
    logger.info(f"Output directory: {config.OUTPUT_DIR}")
    
    uvicorn.run(app, host=host, port=port, loop="asyncio")