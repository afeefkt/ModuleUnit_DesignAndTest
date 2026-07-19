@echo off
REM MUD_MUT Control Center - one-command launch (Windows).
REM Creates a local venv for the launcher, installs Streamlit, starts the UI.
setlocal
cd /d "%~dp0"

set "VENV=.venv-launcher"
if not exist "%VENV%" (
  echo [launch] Creating launcher venv...
  python -m venv "%VENV%"
)
call "%VENV%\Scripts\activate.bat"

echo [launch] Installing Streamlit...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r launcher\requirements.txt

echo [launch] Starting MUD_MUT Control Center at http://localhost:8501
streamlit run launcher\streamlit_app.py
endlocal
