@echo off
setlocal
cd /d "%~dp0"
title Personal Library Indexer

if exist ".venv\Scripts\python.exe" goto check_environment
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv .venv
    goto environment_created
)
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto no_python
python -m venv .venv

:environment_created
if not exist ".venv\Scripts\python.exe" goto setup_failed

:check_environment
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto setup_failed
".venv\Scripts\python.exe" -c "import importlib.metadata as m; assert m.version('pypdf') == '6.20.0'" >nul 2>&1
if not errorlevel 1 goto launch
echo Installing the PDF reader. Internet is needed for this first setup only.
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto setup_failed

:launch
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
exit /b

:no_python
echo Install Python 3.10 or newer from https://www.python.org/downloads/
echo Python 3.12 is recommended. Include Tcl/Tk and select Add Python to PATH.
echo Then run this file again.
pause
exit /b 1

:setup_failed
echo Setup failed. Read the manual setup section in README.md.
echo Check your Internet connection and that Python includes pip and venv.
pause
exit /b 1
