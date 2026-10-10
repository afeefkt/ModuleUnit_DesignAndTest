@echo off
REM MUD_MUT - one-command launch (Windows). No Docker.
REM The platform runs inside WSL (Python venv + gcc/CppUTest/lcov live there);
REM this wrapper just starts launch.sh in WSL. Open http://localhost:8501
REM Forward the cloud-provider API keys (Windows user scope) into WSL.
set "WSLENV=%WSLENV%:OPENROUTER_API_KEY/u:NVIDIA_API_KEY/u:DEEPSEEK_API_KEY/u:GOOGLE_GENERATIVE_AI_API_KEY/u"
wsl.exe --cd "%~dp0" -e bash ./launch.sh
