@echo off
setlocal

rem -----------------------------------------------------------------------------
rem PESE FastAPI Search Engine Launcher
rem Resolves project root from batch file location.
rem -----------------------------------------------------------------------------

set "SCRIPT_DIR=%~dp0"

rem Detect if running from project root, scripts directory, or parent workspace
if exist "%SCRIPT_DIR%engine\.venv\Scripts\python.exe" (
    cd /d "%SCRIPT_DIR%"
) else if exist "%SCRIPT_DIR%..\engine\.venv\Scripts\python.exe" (
    cd /d "%SCRIPT_DIR%.."
) else if exist "%SCRIPT_DIR%PESE\engine\.venv\Scripts\python.exe" (
    cd /d "%SCRIPT_DIR%PESE"
) else (
    rem Fallback directory resolution when venv is not yet created
    if exist "%SCRIPT_DIR%engine" (
        cd /d "%SCRIPT_DIR%"
    ) else if exist "%SCRIPT_DIR%..\engine" (
        cd /d "%SCRIPT_DIR%.."
    ) else if exist "%SCRIPT_DIR%PESE\engine" (
        cd /d "%SCRIPT_DIR%PESE"
    )
)

set "PYTHON_EXE=engine\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo.
    echo PESE Python environment was not found.
    echo.
    echo Expected:
    echo engine\.venv\Scripts\python.exe
    echo.
    echo Please follow docs/installation-guide.md first.
    echo.
    exit /b 1
)

rem Explicit local private configuration
set PESE_PROFILE=private
set PESE_STORAGE_BACKEND=local

echo Starting PESE Python Engine on http://127.0.0.1:8000...
"%PYTHON_EXE%" -m uvicorn engine.api.main:app --host 127.0.0.1 --port 8000 %*
set "EXIT_CODE=%ERRORLEVEL%"

exit /b %EXIT_CODE%
