"""Test execution endpoints"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import subprocess
import logging
from typing import Dict

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

        # Run tests
        run_cmd = [
            "docker", "exec", "cpputest-runner",
            "sh", "-c",
            f"cd /tests/{test_dir.name} && ./run_tests"
        ]

        logger.info(f"Running tests: {' '.join(run_cmd)}")
        run_result = subprocess.run(
            run_cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        # CppUTest returns 0 if all tests pass, non-zero if any fail
        test_status = "passed" if run_result.returncode == 0 else "failed"

        logger.info(f"Tests {test_status}")

        return {
            "status": test_status,
            "build_output": build_result.stdout,
            "build_error": build_result.stderr,
            "test_output": run_result.stdout,
            "test_error": run_result.stderr,
            "exit_code": run_result.returncode
        }

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
