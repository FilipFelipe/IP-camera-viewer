@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo .venv not found. Create it first with: py -m venv .venv
    exit /b 1
)

call .venv\Scripts\activate.bat
python main.py
