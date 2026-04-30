@echo off
REM ============================================================
REM  MUD Tool - Test Runner
REM  Run from repository root: run_tests.bat [quality|unit|all|coverage|live]
REM ============================================================

setlocal

cd /d "%~dp0python-sidecar"
set "PYTHONDONTWRITEBYTECODE=1"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    echo ERROR: Virtual environment not found. Run setup.bat first!
    pause
    exit /b 1
)

echo.
echo Running MUD Tool Tests...
echo ========================
echo.

set "MODE=%~1"
if "%MODE%"=="" set "MODE=quality"
if not "%~1"=="" shift

set "QUALITY_TESTS=tests/unit/test_activity_pipeline_cfg.py tests/unit/test_api_routes.py tests/unit/test_web_generation_quality_ui.py"

echo Mode: %MODE%
echo.

if /I "%MODE%"=="quality" (
    "%PYTHON_EXE%" -m pytest %QUALITY_TESTS% -q %*
) else if /I "%MODE%"=="unit" (
    "%PYTHON_EXE%" -m pytest tests/unit -q %*
) else if /I "%MODE%"=="all" (
    "%PYTHON_EXE%" -m pytest tests -q -k "not live" %*
) else if /I "%MODE%"=="coverage" (
    echo Mode: stable local suite with coverage report
    "%PYTHON_EXE%" -m pytest tests -q -k "not live" --cov=mudtool --cov-report=term-missing %*
) else if /I "%MODE%"=="live" (
    "%PYTHON_EXE%" -m pytest tests -q %*
) else (
    echo Unknown mode: %MODE%
    echo Usage: run_tests.bat [quality^|unit^|all^|coverage^|live]
    exit /b 2
)
set "TEST_EXIT=%ERRORLEVEL%"

echo.
if not "%TEST_EXIT%"=="0" (
    echo Test run finished with failures. Review the first reported errors above.
) else (
    echo Test run completed successfully.
)
echo.
pause
exit /b %TEST_EXIT%
