@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Run SetupEnvironment.bat first.
    pause
    exit /b 1
)
"%~dp0venv\Scripts\python.exe" "%~dp0rename_pdfs.py" "%~dp0input" %*
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
