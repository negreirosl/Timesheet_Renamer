param([string]$Tesseract = "")
$ErrorActionPreference = "Stop"
$Python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
try {
    if (!(Test-Path -LiteralPath $Python)) { throw 'Run SetupEnvironment.bat first.' }
    & $Python -c "import sys, pymupdf; from PIL import Image, ImageOps; print('Python:', sys.executable); print('Imports: OK')"
    if ($LASTEXITCODE -ne 0) { throw 'Python or package imports failed.' }
    & $Python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
    if (!$Tesseract) {
        $Bundled = Join-Path $PSScriptRoot "tools\tesseract\tesseract.exe"
        if (Test-Path -LiteralPath $Bundled) { $Tesseract = $Bundled }
        else {
            $Command = Get-Command tesseract.exe -ErrorAction SilentlyContinue
            if ($Command) { $Tesseract = $Command.Source }
        }
    }
    if (!$Tesseract -or !(Test-Path -LiteralPath $Tesseract)) {
        throw 'Tesseract not found. Supply tools\tesseract runtime, add it to PATH, or use -Tesseract "FULL PATH".'
    }
    & $Tesseract --version
    if ($LASTEXITCODE -ne 0) { throw 'Tesseract executable failed.' }
    $Languages = & $Tesseract --list-langs 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read Tesseract languages.' }
    $Languages | ForEach-Object { Write-Host $_ }
    if (!($Languages | Where-Object { "$($_)".Trim() -eq 'eng' })) { throw 'eng language data unavailable.' }
    Write-Host 'ENVIRONMENT CHECK PASSED. This does not validate OCR crop accuracy.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host "CHECK FAILED: $_" -ForegroundColor Red
    exit 1
}
