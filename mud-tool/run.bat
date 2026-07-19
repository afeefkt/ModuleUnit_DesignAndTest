@echo off
REM ============================================================
REM  MUD Tool - Start Server (Windows)
REM ============================================================
setlocal

echo.
echo  Starting MUD Tool Server...
echo  Press Ctrl+C to stop.
echo.

cd /d "%~dp0python-sidecar"

REM Activate virtual environment
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
) else (
    echo  ERROR: Virtual environment Python not found.
    echo  Run setup.bat first!
    pause
    exit /b 1
)

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo  ERROR: Virtual environment not found.
    echo  Run setup.bat first!
    pause
    exit /b 1
)

REM Check .env
if not exist ".env" (
    echo  WARNING: No .env file found. Using defaults.
    echo  Run setup.bat or copy .env.example to .env
    echo.
)

echo  ------------------------------------------------
echo   MUD Tool Sidecar v0.1.0
echo   Web UI:    http://127.0.0.1:8042/
echo   API Docs:  http://127.0.0.1:8042/docs
echo   Health:    http://127.0.0.1:8042/api/v1/health
echo  ------------------------------------------------
echo.

"%PYTHON_EXE%" -m mudtool.main
