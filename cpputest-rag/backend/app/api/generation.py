"""Test generation endpoints"""

from fastapi import APIRouter, HTTPException, Depends
from pathlib import Path
from typing import List
import time
import json
import logging

from app.models import GenerateTestRequest, TestGenerationResponse, GenerationHistoryResponse
from app.services.test_generator import generate_tests_for_project
from app.services import rag_engine
from app.services.report_generator import generate_html_report
from app.config import config
from app.database import get_db
from fastapi.responses import HTMLResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate-tests", response_model=TestGenerationResponse)
async def generate_tests_endpoint(
    request: GenerateTestRequest,
    db=Depends(get_db)
):
    """Generate CppUTest cases for a project"""
    start_time = time.time()

    if not request.project_path:
        raise HTTPException(status_code=400, detail="project_path is required")

    project_path_str = request.project_path.strip()
    project_path = Path(project_path_str)

    logger.info(f"Request path: {request.project_path}")
    logger.info(f"Path exists: {project_path.exists()}")

    if not project_path.exists():
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

        # Store generation record in database
        project_name = project_path.name
        cursor = await db.execute(
            "SELECT id FROM projects WHERE name = ?", (project_name,)
        )
        project_row = await cursor.fetchone()

        if project_row:
            project_id = project_row[0]
            await db.execute(
                """INSERT INTO generations
                   (project_id, functions_analyzed, tests_generated,
                    failed_functions, output_dir, elapsed_seconds)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    result["functions_analyzed"],
                    result["tests_generated"],
                    json.dumps(result["failed_functions"]),
                    result["output_directory"],
                    elapsed
                )
            )
            await db.commit()

        return TestGenerationResponse(
            status="success",
            elapsed_seconds=elapsed,
            **result
        )
    except Exception as e:
        logger.error(f"Test generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generation-history", response_model=List[GenerationHistoryResponse])
async def get_generation_history(db=Depends(get_db)):
    """Get test generation history"""
    cursor = await db.execute("""
        SELECT g.id, p.name, g.functions_analyzed, g.tests_generated,
               g.failed_functions, g.output_dir, g.elapsed_seconds, g.created_at
        FROM generations g
        JOIN projects p ON g.project_id = p.id
        ORDER BY g.created_at DESC
        LIMIT 50
    """)

    rows = await cursor.fetchall()
    return [
        GenerationHistoryResponse(
            id=row[0],
            project_name=row[1],
            functions_analyzed=row[2],
            tests_generated=row[3],
            failed_functions=json.loads(row[4]) if row[4] else [],
            output_dir=row[5],
            elapsed_seconds=row[6],
            created_at=str(row[7])
        )
        for row in rows
    ]


@router.post("/rebuild-examples-index")
async def rebuild_examples_index_endpoint():
    """Rebuild the RAG examples index"""
    try:
        await rag_engine.build_examples_index()
        return {
            "status": "success",
            "examples_indexed": len(rag_engine.test_examples_metadata.get("texts", []))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-test-report", response_class=HTMLResponse)
async def generate_test_report_endpoint(request: dict):
    """
    Generate an HTML report from test execution results

    Request body should contain:
    - test_result: Dict with test execution results
    - test_directory: Name of the test directory
    - project_path: Optional source project path
    """
    try:
        test_result = request.get("test_result")
        test_directory = request.get("test_directory", "unknown")
        project_path = request.get("project_path")

        if not test_result:
            raise HTTPException(status_code=400, detail="test_result is required")

        html_content = generate_html_report(
            test_result=test_result,
            test_directory=test_directory,
            project_path=project_path
        )

        return HTMLResponse(content=html_content, media_type="text/html")

    except Exception as e:
        logger.error(f"Error generating test report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
