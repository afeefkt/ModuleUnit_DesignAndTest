"""Test execution endpoints"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import subprocess
import logging
from typing import Dict
from app.services.report_generator import generate_html_report

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/run-tests")
async def run_tests(test_directory: str) -> Dict:
    """
    Build and run CppUTest tests in a generated test directory

    Args:
        test_directory: Path to the generated tests directory (e.g., "tests_20260208_153000")

    Returns:
        Dict with build status, test results, and output
    """
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
        # Run docker exec to build tests in the test-runner container
        # Build tests
        build_cmd = [
            "docker", "exec", "cpputest-runner",
            "sh", "-c",
            f"cd /tests/{test_dir.name} && make clean && make"
        ]

        logger.info(f"Building tests: {' '.join(build_cmd)}")
        build_result = subprocess.run(
            build_cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        if build_result.returncode != 0:
            logger.error(f"Build failed: {build_result.stderr}")
            return {
                "status": "build_failed",
                "build_output": build_result.stdout,
                "build_error": build_result.stderr,
                "test_output": None
            }

        # Run tests with coverage generation
        # This will:
        # 1. Run tests with JUnit XML output
        # 2. Generate LCOV coverage data
        # 3. Generate HTML coverage report
        coverage_cmd = [
            "docker", "exec", "cpputest-runner",
            "sh", "-c",
            f"cd /tests/{test_dir.name} && make coverage"
        ]

        logger.info(f"Running tests with coverage: {' '.join(coverage_cmd)}")
        run_result = subprocess.run(
            coverage_cmd,
            capture_output=True,
            text=True,
            timeout=120  # Increased timeout for coverage generation
        )

        # CppUTest returns 0 if all tests pass, non-zero if any fail
        test_status = "passed" if run_result.returncode == 0 else "failed"

        logger.info(f"Tests {test_status}")

        # Check if coverage files were generated
        coverage_info_path = test_dir / "coverage.info"
        coverage_html_dir = test_dir / "coverage_html"
        junit_xml_path = test_dir / "test-results.xml"

        coverage_generated = coverage_info_path.exists()
        html_coverage_generated = coverage_html_dir.exists()
        junit_generated = junit_xml_path.exists()

        if coverage_generated:
            logger.info(f"LCOV coverage report generated: {coverage_info_path}")
        if html_coverage_generated:
            logger.info(f"HTML coverage report generated: {coverage_html_dir}/index.html")
        if junit_generated:
            logger.info(f"JUnit XML report generated: {junit_xml_path}")

        # Prepare test result with coverage information
        test_result = {
            "status": test_status,
            "build_output": build_result.stdout,
            "build_error": build_result.stderr,
            "test_output": run_result.stdout,
            "test_error": run_result.stderr,
            "exit_code": run_result.returncode,
            "coverage_available": coverage_generated,
            "html_coverage_available": html_coverage_generated,
            "junit_xml_available": junit_generated,
            "coverage_info_path": str(coverage_info_path) if coverage_generated else None,
            "coverage_html_path": str(coverage_html_dir / "index.html") if html_coverage_generated else None,
            "junit_xml_path": str(junit_xml_path) if junit_generated else None
        }

        # Automatically generate and save HTML report
        try:
            html_content = generate_html_report(
                test_result=test_result,
                test_directory=test_dir.name,
                project_path=None  # Could be enhanced to track project path
            )

            # Save report to the test directory
            report_path = test_dir / "test-report.html"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"HTML report saved: {report_path}")
            test_result["report_path"] = str(report_path)
            test_result["report_available"] = True

        except Exception as e:
            logger.error(f"Failed to generate HTML report: {e}")
            test_result["report_available"] = False

        return test_result

    except subprocess.TimeoutExpired:
        logger.error("Test execution timed out")
        raise HTTPException(status_code=408, detail="Test execution timed out")
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
