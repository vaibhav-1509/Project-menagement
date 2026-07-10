# One-time project setup: virtual environment, dependencies, database, first Admin account, frontend build.
# Run once from the project root:  .\setup.ps1
# After this finishes, start the whole app (API + UI) with:  .venv\Scripts\python.exe app\main.py

Set-Location $PSScriptRoot

function Invoke-Step {
    # $ErrorActionPreference = "Stop" does NOT catch a non-zero exit code from an
    # external .exe - PowerShell treats that as a normal (non-terminating) return.
    # Without this check, a failed python step would print its traceback and the
    # script would happily continue on to the next step and report success.
    param([string]$Description, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "FAILED: $Description (exit code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "== 1/6 Creating virtual environment (.venv) ==" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    Invoke-Step "venv creation" { python -m venv .venv }
} else {
    Write-Host "  .venv already exists - reusing it."
}
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "== 2/6 Installing dependencies ==" -ForegroundColor Cyan
Invoke-Step "pip upgrade" { & $venvPython -m pip install --upgrade pip --quiet }
Invoke-Step "dependency install" { & $venvPython -m pip install -r requirements.txt }
# Editable install of the local `app` package - this is what makes `import app...`
# work no matter which file/cwd it's run from (fixes ModuleNotFoundError: No module
# named 'app' when a file under app/ is run directly instead of via app.main).
Invoke-Step "editable install of app package" { & $venvPython -m pip install -e . --quiet }

Write-Host "== 3/6 Checking ODBC driver ==" -ForegroundColor Cyan
$driverCheck = & $venvPython -c "import pyodbc; from app.config import settings; print(settings.db_driver in pyodbc.drivers())"
if ($driverCheck -notmatch "True") {
    Write-Host "  WARNING: ODBC driver from .env (DB_DRIVER) was not found on this machine." -ForegroundColor Yellow
    Write-Host "  Install 'Microsoft ODBC Driver 17 for SQL Server' before continuing, or the next step will fail." -ForegroundColor Yellow
}

Write-Host "== 4/6 Creating database and applying schema ==" -ForegroundColor Cyan
Invoke-Step "database creation" { & $venvPython scripts\create_database.py }

Write-Host "== 5/6 Creating first Admin account ==" -ForegroundColor Cyan
Invoke-Step "admin account creation" { & $venvPython scripts\create_admin.py }

Write-Host "== 6/6 Building frontend ==" -ForegroundColor Cyan
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location frontend
    Invoke-Step "frontend dependency install" { npm install }
    Invoke-Step "frontend build" { npm run build }
    Pop-Location
} else {
    Write-Host "  WARNING: npm not found - skipping frontend build." -ForegroundColor Yellow
    Write-Host "  Install Node.js, then run: cd frontend; npm install; npm run build" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Start the app (API + UI, one process) with:"
Write-Host "  .venv\Scripts\python.exe app\main.py"
Write-Host "Then open http://localhost:8000"
