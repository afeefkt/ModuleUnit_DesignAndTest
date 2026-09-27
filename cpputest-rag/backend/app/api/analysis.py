"""Project analysis endpoints"""

from fastapi import APIRouter, Query, HTTPException, Depends
from pathlib import Path
import logging
import json

from app.models import ProjectAnalysisResponse
from app.services.c_parser import analyze_c_project
from app.database import get_db
from app.paths import resolve_project_dir

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/analyze-project", response_model=ProjectAnalysisResponse)
async def analyze_project_endpoint(
    project_path: str = Query(...),
    db=Depends(get_db)
):
    """Analyze a C project and store results in the database"""
    logger.info(f"Analyzing project: {project_path}")
    path = resolve_project_dir(project_path)

    functions = analyze_c_project(path)

    logger.info(f"Analysis complete: found {len(functions)} functions")

    # Build project structure info
    c_files = list(path.rglob("*.c")) + list(path.rglob("*.h"))

    total_lines = 0
    for f in c_files:
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as file:
                total_lines += len(file.readlines())
        except Exception:
            pass

    structure = {
        "files": [str(f.relative_to(path)) for f in c_files],
        "total_lines": total_lines
    }

    # Store in database
    project_name = path.name

    await db.execute(
        "INSERT OR IGNORE INTO projects (name, path) VALUES (?, ?)",
        (project_name, str(path))
    )
    await db.commit()

    cursor = await db.execute(
        "SELECT id FROM projects WHERE name = ?", (project_name,)
    )
    project_row = await cursor.fetchone()
    project_id = project_row[0]

    functions_json = json.dumps([f.dict() for f in functions])
    await db.execute(
        """INSERT INTO analyses (project_id, total_files, total_functions, functions_json)
           VALUES (?, ?, ?, ?)""",
        (project_id, len(c_files), len(functions), functions_json)
    )
    await db.commit()

    return ProjectAnalysisResponse(
        total_files=len(c_files),
        total_functions=len(functions),
        functions=functions,
        project_structure=structure
    )
