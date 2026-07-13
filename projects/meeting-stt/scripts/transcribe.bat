@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

if "%~1"=="" (
    echo Usage: %~nx0 ^<audio file or folder path...^> [--model NAME] [--language ko] ...
    exit /b 1
)

python "%PROJECT_ROOT%\src\stt_transcribe.py" %* --output-dir "%PROJECT_ROOT%\output"
