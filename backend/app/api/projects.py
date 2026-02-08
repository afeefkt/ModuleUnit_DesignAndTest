"""Project management endpoints — listing, upload, debug"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from pathlib import Path
from typing import List
import zipfile
import shutil
import logging
from io import BytesIO

from app.models import ProjectListResponse
from app.config import config
from app.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/projects", response_model=List[ProjectListResponse])
async def list_projects(db=Depends(get_db)):
    """List all registered projects"""
    cursor = await db.execute(
        "SELECT id, name, path, created_at FROM projects ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()

    results = []
    for row in rows:
        # Count C files on disk
        project_path = Path(row[2])
        c_files_count = 0
        if project_path.exists():
            c_files_count = len(
                list(project_path.rglob("*.c")) + list(project_path.rglob("*.h"))
            )

        results.append(ProjectListResponse(
            id=row[0],
            name=row[1],
            path=row[2],
            c_files_count=c_files_count,
            created_at=str(row[3])
        ))

    return results


@router.post("/upload-project")
async def upload_project(
    file: UploadFile = File(...),
    db=Depends(get_db)
):
    """Upload a C project as a zip file"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")

    content = await file.read()

    project_name = file.filename.replace('.zip', '')
    project_path = config.C_PROJECT_DIR / project_name

    if project_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Project '{project_name}' already exists"
        )

    try:
        # Extract zip to c_projects directory
        with zipfile.ZipFile(BytesIO(content)) as zip_file:
            zip_file.extractall(project_path)

        # Register in database
        await db.execute(
            "INSERT INTO projects (name, path) VALUES (?, ?)",
            (project_name, str(project_path))
        )
        await db.commit()

        # Count C files
        c_files = list(project_path.rglob("*.c")) + list(project_path.rglob("*.h"))

        logger.info(f"Uploaded project '{project_name}' with {len(c_files)} C/H files")

        return {
            "status": "success",
            "project_name": project_name,
            "project_path": str(project_path),
            "c_files_count": len(c_files)
        }

    except Exception as e:
        # Cleanup on error
        if project_path.exists():
            shutil.rmtree(project_path)
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/debug/list-projects")
async def list_projects_debug():
    """Debug endpoint to list available projects on disk"""
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
                    "files": [f.name for f in c_files[:10]]
                })

    return {
        "c_project_dir": str(config.C_PROJECT_DIR),
        "c_project_dir_absolute": str(config.C_PROJECT_DIR.absolute()),
        "exists": config.C_PROJECT_DIR.exists(),
        "projects": projects,
        "cwd": str(Path.cwd())
    }
