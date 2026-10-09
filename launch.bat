@echo off
REM MUD_MUT - one-command launch (Windows). No Docker.
REM The platform runs inside WSL (Python venv + gcc/CppUTest/lcov live there);
REM this wrapper just starts launch.sh in WSL. Open http://localhost:8501
wsl.exe --cd "%~dp0" -e bash ./launch.sh
