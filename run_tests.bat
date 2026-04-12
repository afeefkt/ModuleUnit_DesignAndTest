@echo off
REM ============================================================
REM  MUD Tool - Run Tests (Windows)
REM ============================================================

setlocal

cd /d "%~dp0python-sidecar"

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

set "PYTEST_ARGS=tests -v --tb=short --maxfail=10 --durations=10"

if /I "%~1"=="live" (
    shift
    echo Mode: full suite including live/server-backed tests
    echo Expectation: start the sidecar first if you want live HTTP tests to run.
    echo.
    "%PYTHON_EXE%" -m pytest %PYTEST_ARGS% %*
) else (
    echo Mode: stable local suite only
    echo Live integration tests are excluded by default. Use `run_tests.bat live` to include them.
    echo.
    "%PYTHON_EXE%" -m pytest %PYTEST_ARGS% -k "not live" %*
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
