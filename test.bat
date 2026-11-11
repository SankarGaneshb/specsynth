@echo off
setlocal
set SCRIPT_DIR=%~dp0
set VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe

if exist "%VENV_PY%" (
    set PY_EXE="%VENV_PY%"
) else (
    set PY_EXE=python
)

echo ============================================================
echo  Running specsynth test suite using: %PY_EXE%
echo ============================================================

%PY_EXE% -m pytest -v %*
set TEST_EXIT=%ERRORLEVEL%

echo.
echo [*] Cleaning up test caches and temporary artifacts...
%PY_EXE% "%SCRIPT_DIR%scripts\clean.py"

exit /b %TEST_EXIT%
