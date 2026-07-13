# Project Management Tool

A production tracker for 3D asset pipelines. Files move through a sequence of
work stages (e.g. **Polish → GLB → Render**) organized under a Phase /
Category / Sub-Category taxonomy, with each stage independently assigned to a
worker, physically moved between that worker's folders on a Copy-Verify-Delete
transfer pipeline, and fully reported on.

Built for small production teams (studios, freelance pipelines, in-house
asset departments) who currently track this in spreadsheets and need a single
source of truth for "who has what file, at what stage, and is it done."

## What it does

- **Sequential, stage-gated pipeline** - each file goes through an
  admin-defined ordered list of process types (Polish, GLB, Render, or
  whatever your pipeline needs). A stage can't be assigned until the one
  before it is Complete.
- **Multi-role users** - a single account can hold several roles at once
  (e.g. Admin *and* a Polish Artist), so admins can do real assigned work
  alongside managing the team. Role membership is informational; actual
  assignment eligibility comes from each worker's own configured Pending/
  Complete folder pair per process type.
- **Copy-Verify-Delete file transfers** - assigning or completing a stage
  physically moves the file's folder between workers' network paths, with a
  durable checkpoint logged before every filesystem operation and a
  verify-before-delete step, so a crash mid-transfer never silently loses a
  file.
- **Reset / Revoke / Reopen** - three distinct, deliberately different undo
  operations: **Reset** undoes a stage but keeps it in history, **Revoke**
  undoes an assignment that was a mistake and purges it from history/reports,
  **Reopen** is self-service - a worker can undo their own "Complete" and keep
  working, with a real file move back.
- **Universal search & Browse** - a Phase > Category > Sub-Category tree with
  free-text file search, deep-linkable from anywhere in the app.
- **Calendar** - day-by-day assignment/completion/failure activity, scoped to
  your own work unless you're an admin.
- **Reports dashboard** - daily/weekly/monthly/yearly completion charts, a
  per-Phase/Category/Sub-Category completion-progress view, and per-worker or
  whole-team scoping.
- **Audit Trail** - every admin override and manual correction, who did it and
  when.
- **CSV import** - bulk-import files with duplicate detection and per-row
  conflict resolution.

## Stack

- **Backend:** FastAPI + SQLAlchemy, Python 3.10+
- **Database:** Microsoft SQL Server (via `pyodbc` / ODBC Driver 17)
- **Frontend:** React + Vite + AG Grid, built to static assets and served by
  the same FastAPI process - no separate frontend server in production

## Prerequisites

- Windows with PowerShell
- [Python 3.10+](https://www.python.org/downloads/)
- [Node.js LTS](https://nodejs.org/) (for building the frontend)
- A reachable Microsoft SQL Server instance (local or remote) and a login
  with permission to create databases
- [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)

`deploy.ps1` checks for all of these and offers to install what it can via
`winget` - you don't need to have them ready beforehand.

## Deploying

From the project root, in PowerShell:

```powershell
.\deploy.ps1
```

This single script:

1. Creates `.env` on first run, prompting you for your SQL Server host, port,
   database name, and login (copy `.env.example` yourself first if you'd
   rather fill it in by hand).
2. Checks Python, Node.js, and the SQL Server ODBC driver - offers to install
   any that are missing.
3. Creates a virtual environment and installs all Python dependencies.
4. Creates the database (if it doesn't exist yet) and applies the schema.
5. Optionally enables **Transparent Data Encryption** (at-rest disk
   encryption, requires SQL Server Standard/Enterprise/Developer - not
   Express) - see [Encryption](#encryption) below before turning this on.
6. Creates the first **Admin** account and prints its username and password
   to the console **once** - save it immediately, it is never shown again and
   never written to disk.
7. Installs frontend dependencies and builds the production bundle.
8. Prints the command to start the app, and offers to start it right away.

`deploy.ps1` is safe to re-run - every step detects existing state (venv,
database, schema, admin account, frontend build) and reuses it instead of
recreating it, so re-running it after pulling new code just picks up what
changed.

Once deployed, start the app with:

```powershell
.venv\Scripts\python.exe app\main.py
```

and open **http://localhost:8000** - one process serves both the API and the
built UI.

## Encryption

Two independent layers, both optional to reason about separately:

- **In transit** - the app's connection to SQL Server always uses
  `Encrypt=yes` (with `TrustServerCertificate=yes` for a typical self-signed
  local/LAN SQL Server certificate). This is on unconditionally; there's
  nothing to configure.
- **At rest** (Transparent Data Encryption) - encrypts the database's own
  files on disk. Optional, offered during step 5 of `deploy.ps1`, and only
  available on SQL Server Standard, Enterprise, or Developer edition (not
  Express). Enable it later at any time with:

  ```powershell
  .venv\Scripts\python.exe scripts\setup_tde.py
  ```

  The **first time** it runs, it creates a certificate on the SQL Server
  instance and backs it up to `.\tde-backup\` (a `.cer` + `.pvk` file and a
  `README.txt` with the passwords). **That folder is as sensitive as your
  database password** - it's the only way to ever restore a native SQL
  Server backup (`.bak`) of this database on a different or rebuilt SQL
  Server instance. Move it to secure, offline storage and don't leave it
  sitting on this machine. Neither `deploy.ps1` nor `cleanup.ps1` ever reads,
  writes, or deletes anything in `tde-backup\` - it's untouched by both.

  Re-running `.\deploy.ps1` (including after `.\cleanup.ps1` wipes the
  database) reuses the existing certificate automatically, since
  `cleanup.ps1` only drops the app's database, never SQL Server's `master`
  database where the certificate lives.

## Starting over / cleaning up

If a deployment goes wrong partway through and you want a truly clean slate:

```powershell
.\cleanup.ps1
```

This is intentionally separate from `deploy.ps1` and deliberately does **not**
read your `.env` - it asks you to type the SQL Server host, port, database
name, and login by hand, shows a clear warning, and requires you to type the
database name back to confirm before it does anything. It then:

- Drops the database completely (every file record, user, assignment, and
  history entry - **this cannot be undone**; physical files on disk are not
  touched).
- Optionally stops a locally running instance of the app.
- Optionally deletes `.venv`, `frontend\node_modules`, and `frontend\dist` so
  `.\deploy.ps1` performs a completely fresh install.

Run `.\deploy.ps1` again afterward to redeploy from scratch.

## Development

For active frontend development with hot reload (backend on `:8000`,
Vite dev server on `:5173`, each in its own window):

```powershell
.\dev.ps1
```

## Project layout

```
app/                  FastAPI backend (routers, services, models, schemas)
frontend/             React + Vite frontend
scripts/              Database setup, admin bootstrap, password recovery
sql/                  Schema (sql/001_schema.sql)
deploy.ps1            One-command deployment
cleanup.ps1           Full reset (drops the database, optional local wipe)
dev.ps1               Dev-mode launcher (hot reload, two processes)
```
