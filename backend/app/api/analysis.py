"""Project analysis endpoints"""

from fastapi import APIRouter, Query, HTTPException, Depends
from pathlib import Path
import logging
import json

from app.models import ProjectAnalysisResponse
from app.services.c_parser import analyze_c_project
from app.config import config
from app.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/analyze-project", response_model=ProjectAnalysisResponse)
async def analyze_project_endpoint(
    project_path: str = Query(...),
    db=Depends(get_db)
):
    """Analyze a C project and store results in the database"""
    path = Path(project_path)

    logger.info(f"Analyzing project: {project_path}")

    if not path.exists():
        # Try alternative path relative to C_PROJECT_DIR
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

    # Build project structure info
    c_files = list(path.rglob("*.c")) + list(path.rglob("*.h"))

    total_lines = 0
    for f in c_files:
        try:
            with open(f, 'r', errors='ignore') as file:
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
