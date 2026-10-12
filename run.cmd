@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Project environment is missing. See README.md for installation.
  pause
  exit /b 1
)
start "SlateInk" ".venv\Scripts\pythonw.exe" -m slateink
