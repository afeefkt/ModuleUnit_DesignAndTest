"""Test execution endpoints"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import logging
from typing import Dict

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/run-tests")
async def run_tests(test_directory: str) -> Dict:
    """
    Build and run CppUTest tests in a generated test directory (natively, no Docker)

    Args:
        test_directory: Path to the generated tests directory (e.g., "tests_20260208_153000")

    Returns:
        Dict with build status, test results, and output
    """
    from app.services.native_runner import run_tests as _native_run_tests

    # Validate and construct path
    test_dir = Path(test_directory)
    if not test_dir.is_absolute():
        from app.config import config
        test_dir = config.OUTPUT_DIR / test_directory

    if not test_dir.exists():
        raise HTTPException(status_code=404, detail=f"Test directory not found: {test_dir}")

    makefile_path = test_dir / "Makefile"
    if not makefile_path.exists():
        raise HTTPException(status_code=400, detail="No Makefile found in test directory")

    logger.info(f"Building and running tests in: {test_dir}")

    try:
        return _native_run_tests(test_dir)

    except Exception as e:
        logger.error(f"Test execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Test execution failed: {str(e)}")


@router.get("/test-directories")
async def list_test_directories():
    """List all generated test directories"""
    from app.config import config

    if not config.OUTPUT_DIR.exists():
        return {"directories": []}

    test_dirs = [
        {
            "name": d.name,
            "path": str(d),
            "created": d.stat().st_mtime,
            "has_makefile": (d / "Makefile").exists(),
            "test_files": len(list(d.glob("Test_*.cpp")))
        }
        for d in config.OUTPUT_DIR.iterdir()
        if d.is_dir() and d.name.startswith("tests_")
    ]

    # Sort by creation time, newest first
    test_dirs.sort(key=lambda x: x["created"], reverse=True)

    return {"directories": test_dirs}


@router.get("/test-report/{test_directory}")
async def get_test_report(test_directory: str):
    """
    Get HTML report for a test directory
    Returns the HTML report if available
    """
    from app.config import config
    from fastapi.responses import HTMLResponse

    test_dir = config.OUTPUT_DIR / test_directory
    report_path = test_dir / "test-report.html"

    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        return HTMLResponse(content=html_content)

    except Exception as e:
        logger.error(f"Error reading report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read report: {str(e)}")


@router.get("/list-reports")
async def list_reports():
    """List all available test reports with coverage information"""
    from app.config import config

    if not config.OUTPUT_DIR.exists():
        return {"reports": []}

    reports = []
    for test_dir in config.OUTPUT_DIR.iterdir():
        if test_dir.is_dir() and test_dir.name.startswith("tests_"):
            report_path = test_dir / "test-report.html"
            coverage_info = test_dir / "coverage.info"
            coverage_html = test_dir / "coverage_html" / "index.html"
            junit_xml = test_dir / "test-results.xml"

            if report_path.exists():
                reports.append({
                    "test_directory": test_dir.name,
                    "report_path": str(report_path),
                    "created": report_path.stat().st_mtime,
                    "size": report_path.stat().st_size,
                    "has_coverage": coverage_info.exists(),
                    "has_html_coverage": coverage_html.exists(),
                    "has_junit_xml": junit_xml.exists()
                })

    # Sort by creation time, newest first
    reports.sort(key=lambda x: x["created"], reverse=True)

    return {"reports": reports}


@router.get("/coverage-html/{test_directory}/{file_path:path}")
async def get_coverage_html(test_directory: str, file_path: str = "index.html"):
    """
    Get HTML coverage report files
    Serves the entire coverage_html directory
    """
    from app.config import config
    from fastapi.responses import HTMLResponse, FileResponse
    import mimetypes

    test_dir = config.OUTPUT_DIR / test_directory
    coverage_file = test_dir / "coverage_html" / file_path

    if not coverage_file.exists():
        raise HTTPException(status_code=404, detail="Coverage file not found")

    # Determine content type
    content_type, _ = mimetypes.guess_type(str(coverage_file))
    if not content_type:
        content_type = "text/html" if file_path.endswith(".html") else "text/plain"

    try:
        if content_type.startswith("text"):
            with open(coverage_file, 'r', encoding='utf-8') as f:
                content = f.read()
            return HTMLResponse(content=content)
        else:
            return FileResponse(coverage_file, media_type=content_type)

    except Exception as e:
        logger.error(f"Error reading coverage file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read coverage file: {str(e)}")


@router.get("/coverage-lcov/{test_directory}")
async def get_coverage_lcov(test_directory: str):
    """
    Get LCOV coverage data file
    """
    from app.config import config
    from fastapi.responses import FileResponse

    test_dir = config.OUTPUT_DIR / test_directory
    lcov_file = test_dir / "coverage.info"

    if not lcov_file.exists():
        raise HTTPException(status_code=404, detail="LCOV coverage file not found")

    return FileResponse(
        lcov_file,
        media_type="text/plain",
        filename=f"coverage-{test_directory}.info"
    )


@router.get("/junit-xml/{test_directory}")
async def get_junit_xml(test_directory: str):
    """
    Get JUnit XML test results
    """
    from app.config import config
    from fastapi.responses import FileResponse

    test_dir = config.OUTPUT_DIR / test_directory
    junit_file = test_dir / "test-results.xml"

    if not junit_file.exists():
        raise HTTPException(status_code=404, detail="JUnit XML file not found")

    return FileResponse(
        junit_file,
        media_type="application/xml",
        filename=f"junit-{test_directory}.xml"
    )
