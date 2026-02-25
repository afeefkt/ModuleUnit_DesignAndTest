@echo off
REM ============================================================
REM  MUD Tool - Run Tests (Windows)
REM ============================================================

cd /d "%~dp0python-sidecar"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found. Run setup.bat first!
    pause
    exit /b 1
)

echo.
echo Running MUD Tool Tests...
echo ========================
echo.

pytest tests/ -v --tb=short %*

echo.
pause
