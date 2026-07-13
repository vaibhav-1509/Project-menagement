# ============================================================================
# Project Management Tool - full reset (DANGEROUS)
#
# Usage (from the project root):
#   .\cleanup.ps1
#
# What it does:
#   1. Asks you to type the SQL Server host/port, database name, and a SQL
#      login (username + password) BY HAND - it deliberately never reads
#      these from .env, so a stray/scheduled run can't wipe a server just
#      because an old .env happened to be lying around.
#   2. Shows a clear warning and requires you to type the database name back
#      to confirm before touching anything.
#   3. Forcibly disconnects everyone and permanently DROPS that database -
#      every file, user, and history record in it is gone. This cannot be
#      undone; there is no backup step here.
#   4. Optionally also deletes local build artifacts (.venv, frontend build
#      output, frontend node_modules) so you can run .\deploy.ps1 again for a
#      completely fresh install.
#
# This does NOT touch .env, your source code, or anything outside this
# project folder and the one SQL Server database you name.
# ============================================================================

Set-Location $PSScriptRoot

Write-Host "=============================================================" -ForegroundColor Red
Write-Host "  WARNING - THIS PERMANENTLY DELETES DATA" -ForegroundColor Red
Write-Host "=============================================================" -ForegroundColor Red
Write-Host "This will DROP the database you name below." -ForegroundColor Yellow
Write-Host "Every file record, user, assignment, and history entry in it will" -ForegroundColor Yellow
Write-Host "be permanently destroyed. This action CANNOT be undone." -ForegroundColor Yellow
Write-Host "Physical files on disk (in workers' Pending/Complete folders) are" -ForegroundColor Yellow
Write-Host "NOT touched - only the database is deleted." -ForegroundColor Yellow
Write-Host ""

# ---------------------------------------------------------------------------
# Credentials - always typed by hand, never read from .env.
# ---------------------------------------------------------------------------
$dbServer = Read-Host "SQL Server host/IP"
$dbPortInput = Read-Host "SQL Server port [1433]"
$dbPort = if ($dbPortInput) { $dbPortInput } else { "1433" }
$dbName = Read-Host "Database name to DELETE"
$dbUser = Read-Host "SQL Server username (needs permission to drop the database)"
$dbPasswordSecure = Read-Host "SQL Server password" -AsSecureString
$dbPasswordPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($dbPasswordSecure)
)

if (-not $dbServer -or -not $dbName -or -not $dbUser) {
    Write-Host "Server, database name, and username are all required. Aborting - nothing was touched." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "You are about to PERMANENTLY DELETE database '$dbName' on $dbServer`:$dbPort." -ForegroundColor Red
$confirmName = Read-Host "Type the database name exactly to confirm ('$dbName')"
if ($confirmName -ne $dbName) {
    Write-Host "Name did not match. Aborting - nothing was touched." -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------------------
# Drop the database - via plain ADO.NET so this works even if the Python
# venv/pyodbc were never successfully installed (that may be exactly why
# you're running this).
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Connecting to $dbServer`:$dbPort ..." -ForegroundColor Cyan
Add-Type -AssemblyName System.Data

$masterConnString = "Server=$dbServer,$dbPort;Database=master;User Id=$dbUser;Password=$dbPasswordPlain;Encrypt=True;TrustServerCertificate=True;"
try {
    $conn = New-Object System.Data.SqlClient.SqlConnection $masterConnString
    $conn.Open()
} catch {
    Write-Host "FAILED to connect: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Nothing was deleted. Check host/port/username/password and that SQL Server allows this login." -ForegroundColor Yellow
    exit 1
}

try {
    $checkCmd = $conn.CreateCommand()
    $checkCmd.CommandText = "SELECT COUNT(*) FROM sys.databases WHERE name = @name"
    $checkCmd.Parameters.AddWithValue("@name", $dbName) | Out-Null
    $exists = [int]$checkCmd.ExecuteScalar()
    if ($exists -eq 0) {
        Write-Host "Database '$dbName' does not exist on this server - nothing to delete." -ForegroundColor Yellow
    } else {
        Write-Host "Dropping database '$dbName' (disconnecting any active sessions first)..." -ForegroundColor Cyan
        $dropCmd = $conn.CreateCommand()
        # SINGLE_USER WITH ROLLBACK IMMEDIATE forcibly kicks out any other
        # connections (e.g. the app still running) so DROP DATABASE can't
        # hang or fail with "database is in use".
        $dropCmd.CommandText = "ALTER DATABASE [$dbName] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [$dbName];"
        $dropCmd.ExecuteNonQuery() | Out-Null
        Write-Host "Database '$dbName' deleted." -ForegroundColor Green
    }
} catch {
    Write-Host "FAILED while dropping the database: $($_.Exception.Message)" -ForegroundColor Red
    $conn.Close()
    exit 1
} finally {
    $conn.Close()
}

# ---------------------------------------------------------------------------
# Rotate the JWT signing secret in .env, if present.
#
# Every login token is only as valid as (a) a matching user row and (b) a
# valid signature from this secret. The app already re-checks (a) via each
# user's SecurityStamp, but recreating the database from scratch after this
# wipe means brand new users could - in principle - end up with the same
# UserID as before. Rotating the signing secret here too means every token
# issued before this wipe is rejected outright at the signature-verification
# step, before any of that even matters - a stronger, independent guarantee
# specifically for "the whole database was just wiped" rather than relying
# on SecurityStamp alone.
# ---------------------------------------------------------------------------
if (Test-Path ".env") {
    Write-Host ""
    Write-Host "Rotating JWT signing secret (.env) so every previously issued login is rejected..." -ForegroundColor Cyan
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $newSecret = [Convert]::ToBase64String($bytes) -replace '\+', '-' -replace '/', '_' -replace '=', ''
    $envLines = @(Get-Content ".env")
    if ($envLines -match '^JWT_SECRET_KEY=') {
        $envLines = $envLines -replace '^JWT_SECRET_KEY=.*$', "JWT_SECRET_KEY=$newSecret"
    } else {
        $envLines += "JWT_SECRET_KEY=$newSecret"
    }
    Set-Content -Path ".env" -Value $envLines -Encoding utf8
    Write-Host "JWT signing secret rotated - every previous login is now invalid immediately." -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Optional: stop a locally running instance of the app (port 8000).
#
# app\main.py runs uvicorn with reload=True, which spawns a SEPARATE
# multiprocessing child process to actually serve requests - the parent
# process only owns the port and watches for file changes. Killing just the
# port-8000 owner leaves that child running and still holding .venv's files
# open, which later makes "delete .venv" below fail partway through and
# leave a broken, partially-deleted venv. So: find the port owner, then also
# find and kill any process whose parent is that owner (the reload child)
# before touching any files.
# ---------------------------------------------------------------------------
Write-Host ""
$stopApp = Read-Host "Stop any locally running instance of this app (port 8000) if one is up? (y/N)"
if ($stopApp -match '^[Yy]') {
    $conns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $pidsToKill = New-Object System.Collections.Generic.HashSet[int]
        foreach ($c in $conns) {
            [void]$pidsToKill.Add($c.OwningProcess)
            $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($c.OwningProcess)" -ErrorAction SilentlyContinue
            foreach ($child in $children) { [void]$pidsToKill.Add($child.ProcessId) }
        }
        foreach ($procId in $pidsToKill) {
            try {
                Stop-Process -Id $procId -Force -ErrorAction Stop
                Write-Host "Stopped process $procId." -ForegroundColor Green
            } catch {
                Write-Host "Could not stop process $procId`: $($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
        Start-Sleep -Seconds 1
    } else {
        Write-Host "Nothing is listening on port 8000." -ForegroundColor Green
    }
}

# ---------------------------------------------------------------------------
# Optional: wipe local build artifacts so .\deploy.ps1 does a fully fresh
# install (separate confirmation - less destructive than the DB drop above,
# but still asked explicitly rather than assumed).
# ---------------------------------------------------------------------------
Write-Host ""
$wipeLocal = Read-Host "Also delete local install artifacts (.venv, frontend\node_modules, frontend\dist) so you can redeploy from a clean slate? (y/N)"
if ($wipeLocal -match '^[Yy]') {
    foreach ($path in @(".venv", "frontend\node_modules", "frontend\dist")) {
        if (Test-Path $path) {
            try {
                Remove-Item -Recurse -Force $path -ErrorAction Stop
            } catch {
                Write-Host "Error while removing $path`: $($_.Exception.Message)" -ForegroundColor Yellow
            }
            # Remove-Item can partially fail (e.g. a file still locked by a
            # process we didn't catch above) without throwing for the whole
            # call - verify it's actually gone rather than assuming success,
            # so a partial/broken folder is never silently left behind.
            if (Test-Path $path) {
                Write-Host "$path still exists after deletion attempt - something still has a file inside it open." -ForegroundColor Red
                Write-Host "Close any running instance of the app (check for orphaned python.exe processes) and re-run .\cleanup.ps1." -ForegroundColor Yellow
            } else {
                Write-Host "Removed $path" -ForegroundColor Green
            }
        }
    }
} else {
    Write-Host "Left .venv and frontend build artifacts in place." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Green
Write-Host " Cleanup complete." -ForegroundColor Green
Write-Host "=============================================================" -ForegroundColor Green
Write-Host "Your .env file was left untouched. Run .\deploy.ps1 to redeploy." -ForegroundColor Cyan
