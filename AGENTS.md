# AGENTS.md

## What this is

Production tracker for 3D asset pipelines. FastAPI backend + React/Vite frontend, single-process production mode (built UI served by FastAPI). SQL Server via pyodbc.

## Setup

- Run `.\deploy.ps1` first — creates .env, venv, database, schema, admin account, builds frontend.
- `.env` is gitignored; copy `.env.example` and fill in SQL Server details.
- Admin credentials are printed once during deploy and never saved to disk.

## Dev mode

`.\dev.ps1` launches backend (`:8000`) and Vite dev server (`:5173`) in separate windows. Vite proxies `/api` to backend — no CORS config needed in dev.

## Production start

```powershell
.venv\Scripts\python.exe app\main.py
```

Single process serves both API and built UI on `:8000`.

## Lint / typecheck

- **Frontend:** `cd frontend && npm run lint` (oxlint, not eslint)
- **Python:** No linter or typechecker is configured. If you add one, update this file.

## Key gotchas

- `bcrypt` is pinned `<4.1` in requirements.txt — passlib 1.7.4 reads `bcrypt.__about__` which was removed in 4.1. Don't bump it without checking passlib compatibility.
- `tde-backup/` contains encryption certs as sensitive as the DB password. Never commit, never delete via scripts.
- `deploy.ps1` is safe to re-run — it detects existing state and reuses it.
- `cleanup.ps1` drops the database entirely (irreversible). It does NOT touch `.venv`, `node_modules`, or `tde-backup/`.
- Schema lives in `sql/001_schema.sql` — `deploy.ps1` applies it.

## Structure

- `app/` — FastAPI backend: routers, services, models, schemas, security, config, database
- `frontend/` — React + Vite + AG Grid + Recharts
- `scripts/` — DB setup, admin bootstrap, password recovery, TDE setup
- `sql/` — Schema SQL
- `draco/` — Vendored model-viewer library (not part of the app build)
