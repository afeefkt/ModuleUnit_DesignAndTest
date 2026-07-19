@echo off
setlocal

cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
  echo Please create/setup the sidecar environment first.
  echo From repo root, run setup.bat first.
  exit /b 1
)

echo Running EPS flowchart diagnostic...
echo.
echo Sidecar: %CD%
echo Python:  .venv\Scripts\python.exe
echo.

".venv\Scripts\python.exe" "tools\diagnose_eps_flowchart_pipeline.py" %*
set EXIT_CODE=%ERRORLEVEL%

echo.
if %EXIT_CODE% EQU 0 (
  echo Diagnostic completed successfully.
) else (
  echo Diagnostic finished with errors. Check the generated report under output\diagnostics.
)

exit /b %EXIT_CODE%
