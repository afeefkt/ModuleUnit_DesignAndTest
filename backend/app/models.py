"""Pydantic models for request/response schemas"""

from pydantic import BaseModel
from typing import List, Dict, Optional, Any


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


class ProjectListResponse(BaseModel):
    id: int
    name: str
    path: str
    c_files_count: int = 0
    created_at: str


class GenerationHistoryResponse(BaseModel):
    id: int
    project_name: str
    functions_analyzed: int
    tests_generated: int
    failed_functions: List[str]
    output_dir: str
    elapsed_seconds: float
    created_at: str
