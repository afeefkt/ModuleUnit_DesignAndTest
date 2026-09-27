@echo off
REM MUD_MUT Control Center - one-command launch (Windows).
REM Starts Docker services (mud-tool + cpputest-rag + test-runner + Ollama),
REM then opens the Streamlit Control Center. Stops Docker services on exit.
setlocal
cd /d "%~dp0"

REM ── 1. Make sure the Docker engine is up (start Docker Desktop if needed) ──
docker info >nul 2>nul
if not errorlevel 1 goto docker_ok
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
  echo [launch] Docker engine not running - starting Docker Desktop...
  start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
) else (
  echo [launch] Docker engine not running - please start Docker Desktop.
)
set /a DOCKER_WAIT=0
:wait_docker
timeout /t 2 /nobreak >nul
docker info >nul 2>nul
if not errorlevel 1 goto docker_ok
set /a DOCKER_WAIT+=1
if %DOCKER_WAIT% lss 60 goto wait_docker
echo [launch] ERROR: Docker is still not reachable after 2 minutes.
echo [launch]        Start Docker Desktop and re-run. Continuing to Streamlit for status.
:docker_ok

REM ── 2. Pick the Ollama mode ──────────────────────────────────────────────────
REM Native Ollama already on :11434 (your pulled models) -> containers use it.
REM Otherwise start the bundled Ollama container (+ GPU override if NVIDIA).
set "COMPOSE_ARGS=-f docker-compose.yml"
curl.exe -fs -o nul http://localhost:11434/api/tags
if not errorlevel 1 (
  echo [launch] Native Ollama detected on :11434 - containers will use it.
  goto ollama_ok
)
echo [launch] No Ollama on the host - starting the bundled Ollama container.
set "DOCKER_OLLAMA_BASE=http://ollama:11434"
set "COMPOSE_ARGS=-f docker-compose.yml --profile bundled-ollama"
nvidia-smi >nul 2>nul
if errorlevel 1 goto ollama_ok
set "COMPOSE_ARGS=-f docker-compose.yml -f docker-compose.gpu.yml --profile bundled-ollama"
echo [launch] NVIDIA GPU detected - bundled Ollama will use it.
:ollama_ok

REM ── 3. Start backend services ──────────────────────────────────────────────
echo [launch] Starting Docker services (mud-tool, cpputest-rag)...
docker compose %COMPOSE_ARGS% up -d --build
if errorlevel 1 (
  echo [launch] WARNING: docker compose up failed - see the output above.
  echo [launch]          Continuing to Streamlit anyway.
)

REM ── 4. Create launcher venv if needed ─────────────────────────────────────
set "VENV=.venv-launcher"
if not exist "%VENV%" (
  echo [launch] Creating launcher venv...
  python -m venv "%VENV%"
)
call "%VENV%\Scripts\activate.bat"

echo [launch] Installing Streamlit...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r launcher\requirements.txt

REM ── 5. Run Streamlit (blocking) ───────────────────────────────────────────
echo [launch] Starting MUD_MUT Control Center at http://localhost:8501
echo [launch] Press Ctrl+C to stop, then answer N to "Terminate batch job (Y/N)?"
echo [launch] so the Docker services below get shut down.
streamlit run launcher\streamlit_app.py

REM ── 6. Tear down Docker services when Streamlit exits ─────────────────────
echo.
echo [launch] Stopping Docker services...
docker compose %COMPOSE_ARGS% down
endlocal
