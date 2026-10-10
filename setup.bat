@echo off
REM MUD_MUT - one-time setup (Windows). No Docker.
REM Everything is installed inside WSL; this wrapper runs setup.sh there.
REM If the toolchain check reports missing packages, run (once, as root):
REM   wsl -u root -e apt-get install -y build-essential cpputest lcov
set "WSLENV=%WSLENV%:OPENROUTER_API_KEY/u:NVIDIA_API_KEY/u:DEEPSEEK_API_KEY/u:GOOGLE_GENERATIVE_AI_API_KEY/u"
wsl.exe --cd "%~dp0" -e bash ./setup.sh
pause
