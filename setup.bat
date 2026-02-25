@echo off
REM ============================================================
REM  MUD Tool - Windows Setup Script
REM  AI-Assisted AUTOSAR Module & Unit Design
REM ============================================================
setlocal enabledelayedexpansion

echo.
echo  ================================================================
echo   MUD Tool Setup - AUTOSAR Module ^& Unit Design
echo  ================================================================
echo.

REM ── Check Python ────────────────────────────────────────
echo [1/6] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.11+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Found Python %PYVER%

REM ── Create virtual environment ──────────────────────────
echo.
echo [2/6] Creating Python virtual environment...
cd /d "%~dp0python-sidecar"

if not exist ".venv" (
    python -m venv .venv
    echo  Virtual environment created at python-sidecar\.venv
) else (
    echo  Virtual environment already exists, skipping.
)

REM ── Activate venv and install dependencies ──────────────
echo.
echo [3/6] Installing Python dependencies...
call .venv\Scripts\activate.bat

pip install --upgrade pip >nul 2>&1
pip install -e ".[dev]"
if errorlevel 1 (
    echo  ERROR: Failed to install dependencies.
    pause
    exit /b 1
)
echo  All Python dependencies installed.

REM ── Setup .env file ─────────────────────────────────────
echo.
echo [4/6] Setting up configuration...
cd /d "%~dp0python-sidecar"
if not exist ".env" (
    copy .env.example .env >nul
    echo  Created .env from template.
    echo  IMPORTANT: Edit python-sidecar\.env and add your ANTHROPIC API key!
    echo.
    echo  Get your API key from: https://console.anthropic.com/settings/keys
) else (
    echo  .env already exists, skipping.
)

REM ── Create output directories ───────────────────────────
echo.
echo [5/6] Creating data directories...
cd /d "%~dp0"
if not exist "data" mkdir data
if not exist "output" mkdir output
echo  Directories ready.

REM ── Check Java (optional for Modelio plugin) ───────────
echo.
echo [6/6] Checking Java installation (optional)...
java -version >nul 2>&1
if errorlevel 1 (
    echo  Java not found. Modelio plugin requires Java 17+.
    echo  The Python sidecar works standalone without Java.
) else (
    for /f "tokens=3 delims= " %%v in ('java -version 2^>^&1 ^| findstr /i "version"') do set JAVAVER=%%v
    echo  Found Java !JAVAVER!

    REM Check Maven
    mvn --version >nul 2>&1
    if errorlevel 1 (
        echo  Maven not found. Install Maven to build the Modelio plugin.
    ) else (
        echo  Maven found. You can build the Modelio plugin with: cd modelio-plugin ^&^& mvn compile
    )
)

echo.
echo  ================================================================
echo   Setup Complete!
echo  ================================================================
echo.
echo  NEXT STEPS:
echo.
echo  1. Edit your API key:
echo     notepad python-sidecar\.env
echo     (Set MUD_ANTHROPIC_API_KEY=sk-ant-your-actual-key)
echo.
echo  2. Start the server:
echo     run.bat
echo.
echo  3. Open the API docs in your browser:
echo     http://127.0.0.1:8042/docs
echo.
echo  4. Try importing sample requirements:
echo     curl -X POST http://127.0.0.1:8042/api/v1/requirements/import ^
echo       -F "file=@data/sample/sample_requirements.csv"
echo.

pause
