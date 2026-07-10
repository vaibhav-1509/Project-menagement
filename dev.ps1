# Runs the backend (FastAPI, hot reload, :8000) and frontend (Vite dev server,
# :5173) together for active development - each in its own PowerShell window so
# their logs don't interleave and you can Ctrl+C one without killing the other.
# Usage:  .\dev.ps1
#
# This is for frontend development with hot reload. For the single-process
# production-style deploy (one process serves the built UI + API), just run:
#   .venv\Scripts\python.exe app\main.py

Set-Location $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "No .venv found - run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "npm not found - install Node.js first." -ForegroundColor Red
    exit 1
}

Write-Host "Starting backend  (FastAPI, :8000) in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$PSScriptRoot'; & '$venvPython' app\main.py"
)

Write-Host "Starting frontend (Vite dev server, :5173) in a new window..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$PSScriptRoot\frontend'; npm run dev"
)

Write-Host ""
Write-Host "Backend:  http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "(each is running in its own window - close that window or Ctrl+C in it to stop)"
