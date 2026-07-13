# ============================================================================
# Project Management Tool - single-command deployment
#
# Usage (from the project root):
#   .\deploy.ps1
#
# What it does, in order:
#   1. Creates .env (from .env.example) if missing, prompting for SQL Server
#      connection details and anything else required.
#   2. Checks prerequisites (Python, Node.js, ODBC Driver 17 for SQL Server)
#      and offers to install any that are missing via winget.
#   3. Creates a virtual environment and installs all Python dependencies.
#   4. Creates the database (if missing) and applies/updates the schema.
#   5. Optionally enables Transparent Data Encryption (at-rest, requires SQL
#      Server Standard/Enterprise/Developer - skips itself on Express).
#   6. Creates the first Admin account and prints its password ONCE.
#      (Skipped automatically if an Admin already exists.)
#   7. Installs frontend dependencies and builds the production bundle.
#   8. Prints how to start the app.
#
# Safe to re-run: every step is idempotent (existing venv/database/admin/
# frontend build are detected and reused rather than recreated).
# ============================================================================

Set-Location $PSScriptRoot

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Invoke-Step {
    # $ErrorActionPreference = "Stop" does NOT catch a non-zero exit code from an
    # external .exe - PowerShell treats that as a normal (non-terminating) return.
    # Without this check, a failed python/npm step would print its traceback and
    # the script would happily continue on and report overall success.
    param([string]$Description, [scriptblock]$Command)
    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "FAILED: $Description (exit code $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

function Test-WingetAvailable {
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

function Install-WithWinget {
    param([string]$DisplayName, [string]$WingetId, [string]$ManualUrl)
    if (-not (Test-WingetAvailable)) {
        Write-Host "  winget is not available on this machine." -ForegroundColor Yellow
        Write-Host "  Install $DisplayName manually: $ManualUrl" -ForegroundColor Yellow
        return $false
    }
    $answer = Read-Host "  Install $DisplayName now via winget? (y/N)"
    if ($answer -notmatch '^[Yy]') {
        Write-Host "  Skipped. Install $DisplayName manually: $ManualUrl" -ForegroundColor Yellow
        return $false
    }
    try {
        winget install --id $WingetId --accept-source-agreements --accept-package-agreements -e
        return $true
    } catch {
        Write-Host "  winget install failed. Install $DisplayName manually: $ManualUrl" -ForegroundColor Yellow
        return $false
    }
}

Write-Host "=============================================================" -ForegroundColor Green
Write-Host " Project Management Tool - Deployment" -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 1/8 - .env
# ---------------------------------------------------------------------------
Write-Step "1/8 Checking .env configuration"

if (-not (Test-Path ".env")) {
    Write-Host "  No .env found - let's create one." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
    }

    Write-Host ""
    Write-Host "  Enter your SQL Server connection details (used to create/connect to the database)." -ForegroundColor Cyan
    $dbServer = Read-Host "  SQL Server host/IP (e.g. localhost or 192.168.1.10)"
    $dbPortInput = Read-Host "  SQL Server port [1433]"
    $dbPort = if ($dbPortInput) { $dbPortInput } else { "1433" }
    $dbNameInput = Read-Host "  Database name [ProjectManagement]"
    $dbName = if ($dbNameInput) { $dbNameInput } else { "ProjectManagement" }
    $dbUser = Read-Host "  SQL Server username (e.g. sa)"
    $dbPasswordSecure = Read-Host "  SQL Server password" -AsSecureString
    $dbPasswordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbPasswordSecure)
    )
    $corsInput = Read-Host "  Frontend origin(s) for CORS, comma-separated [http://localhost:8000]"
    $corsOrigins = if ($corsInput) { $corsInput } else { "http://localhost:8000" }

    $envLines = @(
        "DB_SERVER=$dbServer",
        "DB_PORT=$dbPort",
        "DB_NAME=$dbName",
        "DB_USER=$dbUser",
        "DB_PASSWORD=$dbPasswordPlain",
        "DB_DRIVER=ODBC Driver 17 for SQL Server",
        "",
        "JWT_SECRET_KEY=",
        "JWT_ALGORITHM=HS256",
        "JWT_EXPIRES_MINUTES=480",
        "",
        "CORS_ORIGINS_RAW=$corsOrigins"
    )
    Set-Content -Path ".env" -Value $envLines -Encoding utf8
    Write-Host "  .env written. (JWT_SECRET_KEY will be generated automatically on first run.)" -ForegroundColor Green
} else {
    Write-Host "  .env already exists - reusing it." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 2/8 - Python + virtual environment + dependencies
# ---------------------------------------------------------------------------
Write-Step "2/8 Python environment and dependencies"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "  Python was not found on PATH." -ForegroundColor Red
    Install-WithWinget -DisplayName "Python 3.12" -WingetId "Python.Python.3.12" -ManualUrl "https://www.python.org/downloads/"
    Write-Host "  Re-open this terminal after installing Python, then re-run .\deploy.ps1" -ForegroundColor Yellow
    exit 1
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if ((Test-Path ".venv") -and -not (Test-Path $venvPython)) {
    # .venv exists but is missing its own interpreter - a partial/corrupted
    # venv (e.g. an earlier install or cleanup got interrupted, often by
    # antivirus or a running process holding a file open) rather than a
    # working one. Trusting it as-is would fail three steps later with a
    # confusing "term not recognized" error, so rebuild it now instead.
    Write-Host "  .venv exists but looks incomplete (no Scripts\python.exe) - recreating it." -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".venv"
}

if (-not (Test-Path ".venv")) {
    Invoke-Step "venv creation" { python -m venv .venv }
} else {
    Write-Host "  .venv already exists - reusing it." -ForegroundColor Green
}

if (-not (Test-Path $venvPython)) {
    Write-Host "  venv creation did not produce $venvPython - something is wrong with this Python install." -ForegroundColor Red
    exit 1
}

Invoke-Step "pip upgrade" { & $venvPython -m pip install --upgrade pip --quiet }
Invoke-Step "dependency install" { & $venvPython -m pip install -r requirements.txt }
# Editable install of the local `app` package - this is what makes `import app...`
# work no matter which file/cwd it's run from.
Invoke-Step "editable install of app package" { & $venvPython -m pip install -e . --quiet }

# ---------------------------------------------------------------------------
# Step 3/8 - ODBC Driver for SQL Server
# ---------------------------------------------------------------------------
Write-Step "3/8 Checking ODBC Driver for SQL Server"

$driverCheck = & $venvPython -c "import pyodbc; from app.config import settings; print(settings.db_driver in pyodbc.drivers())"
if ($driverCheck -notmatch "True") {
    Write-Host "  The ODBC driver configured in .env (DB_DRIVER) was not found on this machine." -ForegroundColor Yellow
    Install-WithWinget -DisplayName "Microsoft ODBC Driver 17 for SQL Server" -WingetId "Microsoft.msodbcsql.17" `
        -ManualUrl "https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server"
    Write-Host "  Re-run .\deploy.ps1 after installing the driver." -ForegroundColor Yellow
} else {
    Write-Host "  ODBC driver found." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Step 4/8 - Database + schema
# ---------------------------------------------------------------------------
Write-Step "4/8 Creating database and applying schema"

$dbServerForCheck = (Get-Content ".env" | Where-Object { $_ -match '^DB_SERVER=' }) -replace '^DB_SERVER=', ''
$dbPortForCheck = (Get-Content ".env" | Where-Object { $_ -match '^DB_PORT=' }) -replace '^DB_PORT=', ''
if ($dbServerForCheck -and $dbPortForCheck) {
    $portTest = Test-NetConnection -ComputerName $dbServerForCheck -Port $dbPortForCheck -WarningAction SilentlyContinue
    if (-not $portTest.TcpTestSucceeded) {
        Write-Host "  Cannot reach $dbServerForCheck`:$dbPortForCheck - is SQL Server running and reachable from this machine?" -ForegroundColor Red
        Write-Host "  Check DB_SERVER/DB_PORT in .env, firewall rules, and that SQL Server allows remote/TCP connections." -ForegroundColor Yellow
        exit 1
    }
}
Invoke-Step "database creation" { & $venvPython scripts\create_database.py }

# ---------------------------------------------------------------------------
# Step 5/8 - Transparent Data Encryption (optional, at-rest encryption)
# ---------------------------------------------------------------------------
Write-Step "5/8 Transparent Data Encryption (optional)"
Write-Host "  Encrypts the database's own files on disk (separate from the TLS" -ForegroundColor Cyan
Write-Host "  connection already in place). Requires SQL Server Standard, Enterprise," -ForegroundColor Cyan
Write-Host "  or Developer edition - not supported on Express." -ForegroundColor Cyan
$enableTde = Read-Host "  Enable Transparent Data Encryption now? (y/N)"
if ($enableTde -match '^[Yy]') {
    Invoke-Step "TDE setup" { & $venvPython scripts\setup_tde.py }
    Write-Host "  If a new certificate was just created, its backup is in .\tde-backup\ -" -ForegroundColor Yellow
    Write-Host "  move that folder to secure OFFLINE storage. See tde-backup\README.txt." -ForegroundColor Yellow
} else {
    Write-Host "  Skipped. Re-run .\deploy.ps1 later to enable it, or run:" -ForegroundColor Yellow
    Write-Host "  .venv\Scripts\python.exe scripts\setup_tde.py" -ForegroundColor Cyan
}

# ---------------------------------------------------------------------------
# Step 6/8 - First Admin account
# ---------------------------------------------------------------------------
Write-Step "6/8 Creating first Admin account"
Invoke-Step "admin account creation" { & $venvPython scripts\create_admin.py }

# ---------------------------------------------------------------------------
# Step 7/8 - Node.js + frontend dependencies
# ---------------------------------------------------------------------------
Write-Step "7/8 Frontend dependencies"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "  Node.js/npm was not found on PATH." -ForegroundColor Red
    $installed = Install-WithWinget -DisplayName "Node.js LTS" -WingetId "OpenJS.NodeJS.LTS" -ManualUrl "https://nodejs.org/"
    if (-not $installed -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
        Write-Host "  Re-open this terminal after installing Node.js, then re-run .\deploy.ps1" -ForegroundColor Yellow
        exit 1
    }
}

Push-Location frontend
Invoke-Step "frontend dependency install" { npm install }

# ---------------------------------------------------------------------------
# Step 8/8 - Frontend build
# ---------------------------------------------------------------------------
Write-Step "8/8 Building frontend for production"
Invoke-Step "frontend build" { npm run build }
Pop-Location

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Green
Write-Host " Deployment complete." -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Start the app (API + built UI, single process):"
Write-Host "  .venv\Scripts\python.exe app\main.py" -ForegroundColor Cyan
Write-Host "Then open:"
Write-Host "  http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "If this is a fresh install, your Admin username/password were printed above -" -ForegroundColor Yellow
Write-Host "save them now, they will not be shown again." -ForegroundColor Yellow

$startNow = Read-Host "Start the app now? (y/N)"
if ($startNow -match '^[Yy]') {
    & $venvPython app\main.py
}
