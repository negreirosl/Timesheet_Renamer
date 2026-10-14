@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Run SetupEnvironment.bat first.
    pause
    exit /b 1
)
echo This renames PDFs in input. Verify dry-run crops and names first.
set /p "CONFIRM=Type YES to continue: "
if /I not "%CONFIRM%"=="YES" exit /b 0
"%~dp0venv\Scripts\python.exe" "%~dp0rename_pdfs.py" "%~dp0input" --apply %*
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
