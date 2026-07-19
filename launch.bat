@echo off
REM MUD_MUT Control Center - one-command launch (Windows).
REM Starts Docker services (mud-tool + cpputest-rag + test-runner + Ollama),
REM then opens the Streamlit Control Center. Stops Docker services on exit.
setlocal
cd /d "%~dp0"

REM ── 1. Start backend services ──────────────────────────────────────────────
echo [launch] Starting Docker services (mud-tool, cpputest-rag, ollama)...
docker compose up -d --build
if errorlevel 1 (
  echo [launch] WARNING: docker compose up failed. Services may not be available.
  echo [launch]          Is Docker Desktop running? Continuing to Streamlit anyway.
)

REM ── 2. Create launcher venv if needed ─────────────────────────────────────
set "VENV=.venv-launcher"
if not exist "%VENV%" (
  echo [launch] Creating launcher venv...
  python -m venv "%VENV%"
)
call "%VENV%\Scripts\activate.bat"

echo [launch] Installing Streamlit...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r launcher\requirements.txt

REM ── 3. Run Streamlit (blocking) ───────────────────────────────────────────
echo [launch] Starting MUD_MUT Control Center at http://localhost:8501
echo [launch] Press Ctrl+C to stop. Docker services will be shut down on exit.
streamlit run launcher\streamlit_app.py

REM ── 4. Tear down Docker services when Streamlit exits ─────────────────────
echo.
echo [launch] Stopping Docker services...
docker compose down
endlocal
