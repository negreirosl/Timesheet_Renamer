param([string]$PythonExe = "")
$ErrorActionPreference = "Stop"
$Workspace = $PSScriptRoot
$Venv = Join-Path $Workspace "venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
try {
    if (!(Test-Path -LiteralPath $VenvPython)) {
        if (!$PythonExe) {
            $Candidates = @(
                (Join-Path (Split-Path $Workspace -Parent) "WinPython\python\python.exe"),
                (Join-Path $Workspace "WinPython\python\python.exe"),
                "C:\Radio Room\crew_dashboard\WinPython\python\python.exe"
            )
            foreach ($Candidate in $Candidates) {
                if (Test-Path -LiteralPath $Candidate) { $PythonExe = $Candidate; break }
            }
        }
        if (!$PythonExe -or !(Test-Path -LiteralPath $PythonExe)) {
            throw 'Base Python not found. Run SetupEnvironment.ps1 -PythonExe "FULL PATH TO python.exe".'
        }
        Write-Host "Creating renamer environment using: $PythonExe"
        & $PythonExe -m venv $Venv
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    Write-Host "Installing dependencies into: $VenvPython"
    & $VenvPython -m pip install -r (Join-Path $Workspace "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $VenvPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
    Write-Host 'Setup completed. No recycle, freeze, or offline mode.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host "SETUP FAILED: $_" -ForegroundColor Red
    exit 1
}
