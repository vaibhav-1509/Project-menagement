# Project Management Tool — Architecture Plan

10-user 3D production tracker. Files move through three phases — **Polish → GLB → Render** — each with its own SMB folder tree (`Pending / InProgress / Complete`). Backend: FastAPI. DB: SQL Server. Frontend: AG-Grid.

## 1. Database Schema (3NF)

Lookup tables are split out so no status/role/phase name is ever stored as a free-text magic string, and every many-valued attribute (versions, audit history, transfer steps) gets its own table instead of living as repeating columns on `Files`.

```
Roles            RoleID PK, RoleName UNIQUE
Phases           PhaseID PK, PhaseName UNIQUE            -- Polish, GLB, Render
FileStatuses     StatusID PK, StatusName UNIQUE           -- Pending, InProgress, Transferring, Complete, Locked, Error
Categories       CategoryID PK, PhaseID FK, CategoryName    UNIQUE(PhaseID, CategoryName)
                 -- scoped per phase: Polish/GLB/Render each define their own category
                 -- list; the same name in two phases is two different rows
SubCategories    SubCategoryID PK, CategoryID FK, SubCategoryName    UNIQUE(CategoryID, SubCategoryName)

Users            UserID PK, Username UNIQUE, PasswordHash, RoleID FK,
                 PhaseID FK NULL,        -- which phase this artist works (NULL for Admin)
                 IsActive BIT, CreatedAt

PhasePaths       PhasePathID PK, PhaseID FK UNIQUE, RootPath NVARCHAR(500)
                 -- e.g. Z:\Polish_Folder\ ; Pending/InProgress/Complete/<Username> are
                 -- conventions computed under this root, not stored per-row

ImportBatches    ImportBatchID PK, ImportedByUserID FK, ImportedAt, SourceCsvName

Files            FileID PK, FileName NVARCHAR(255), PhaseID FK, CategoryID FK NULL,
                 SubCategoryID FK NULL, StatusID FK, AssignedToUserID FK NULL,
                 CurrentVersionID FK NULL -> FileVersions.VersionID,
                 CreatedAt, UpdatedAt
                 UNIQUE(FileName, PhaseID)

FileVersions     VersionID PK, FileID FK, VersionNumber INT, SourcePath NVARCHAR(500),
                 ImportBatchID FK, CreatedAt
                 UNIQUE(FileID, VersionNumber)

TaskAssignments  AssignmentID PK, FileID FK, VersionID FK, AssignedToUserID FK,
                 PhaseID FK, StatusID FK, AssignedTS, CompletionTS NULL, IsActive BIT
                 -- IsActive lets a file have exactly one live assignment; resets flip
                 -- IsActive=0 and write an AuditTrail row rather than deleting history

AuditTrail       AuditTrailID PK, FileID FK, AssignmentID FK NULL, Action NVARCHAR(50),
                 PerformedByUserID FK, OldValue NVARCHAR(MAX) NULL, NewValue NVARCHAR(MAX) NULL,
                 Timestamp
                 -- Admin resets / manual completion-time edits land here, verbatim

FileTransferLog  TransferID PK, FileID FK, AssignmentID FK NULL, SourcePath, DestPath,
                 Step NVARCHAR(20),      -- Copy | Verify | Delete
                 Status NVARCHAR(20),    -- Started | Success | Failed
                 ErrorMessage NULL, Timestamp
                 -- Durable record of the Copy-Verify-Delete pipeline; used for crash
                 -- recovery (see §2) and for surfacing "File Locked" errors to the UI
```

Normalization notes:
- Roles/Phases/Statuses/Categories are lookups (2NF/3NF) — filtering and RBAC checks join on IDs, never string-compare.
- Versioning lives in `FileVersions`, not as columns on `Files` — "Overwrite" updates `Files.CurrentVersionID`, "New Version" inserts a row and repoints it, "Skip" does neither. Full version history is preserved either way.
- `TaskAssignments` is the *live* assignment; `AuditTrail` is the append-only history. Resetting a file never deletes a row — it deactivates the assignment and archives the delta.

## 2. API Workflow — "Copy-Verify-Delete" (file assignment)

`POST /api/admin/files/{file_id}/assign  { user_id }`

The filesystem move and the DB write are not one atomic operation (SQL Server can't transaction a SMB copy), so the pipeline is a **durable state machine**: every step is logged to `FileTransferLog` *before* it's attempted, so a crash mid-copy is recoverable on restart instead of silently corrupting state.

1. **Validate** — file status is assignable, target user is active and belongs to the file's phase.
2. **DB txn A (fast, commits immediately):**
   - `Files.StatusID = Transferring`
   - insert `TaskAssignments` row (`StatusID = Transferring`)
   - insert `FileTransferLog(Step=Copy, Status=Started)`
   - This is the durability checkpoint — if the process dies right after this, a reconciliation job on startup finds the orphaned `Transferring` row and re-drives or flags it.
3. **Copy** — `source_path` from `FileVersions.SourcePath`, `dest_path = PhasePaths.RootPath + \Pending\ + Username + \ + FileName`. Copy via `shutil.copytree` (or `robocopy` subprocess for large SMB trees).
   - `PermissionError` / locked handle → log `FileTransferLog(Step=Copy, Status=Failed, ErrorMessage='File Locked')`, revert `Files.StatusID` to prior value, return **409 File Locked**. Source is never touched on this path.
4. **Verify** — recursively compare file count + total byte size (or checksums for small trees) between source and dest.
   - Mismatch → delete the *partial destination copy only*, log `Verify Failed`, revert state, return error. **Source is still untouched.**
5. **Delete source** — only reached once verification passed. If delete fails (e.g. still locked), the verified copy at the destination already exists, so this is not a data-loss condition — log `Delete Failed` as a warning for manual cleanup, but proceed to step 6 anyway.
6. **DB txn B (commits the outcome):**
   - `Files.StatusID = Pending`, `Files.AssignedToUserID = user_id`
   - `TaskAssignments.StatusID = Pending`
   - `FileTransferLog(Step=Delete, Status=Success)`
7. Return `200` with the assignment record.

**Invariant enforced throughout:** the source folder is deleted in exactly one place (step 5), and only after step 4 has logged a `Verify: Success`. No other code path touches `shutil.rmtree` on a source path.

**Completion flow** (`POST /api/artist/assignments/{id}/complete`) is the same shape without a filesystem copy: move dest folder from the user's `InProgress` to `Complete` subfolder (or `Pending` → `Complete` if no explicit in-progress step is used), stamp `CompletionTS = now`, `TaskAssignments.StatusID = Complete`.

**Reset flow** (`POST /api/admin/files/{file_id}/reset`): sets `TaskAssignments.IsActive = 0`, writes an `AuditTrail` row capturing the prior assignment, and flips `Files.StatusID` back to `Pending` — no physical file move by default (folder stays where it is; admin can re-trigger assignment separately).

## 3. UI Layout — Command Center

```
┌─────────────────────────────────────────────────────────────────┐
│ Logo   Project Management Tool          [Role Badge] [User ▾]   │
├───────────────┬───────────────────────────────────────────────--┤
│ Dashboard     │ Filter bar: Phase ▾ Category ▾ Sub-Category ▾    │
│ Import CSV    │             Status ▾ Assigned To ▾ (admin only)  │
│ Reports       ├───────────────────────────────────────────────--┤
│ Calendar      │  AG-Grid                                        │
│ Audit Trail † │  File Name | Phase | Category | Sub-Cat | Ver   │
│ Settings †    │  | Status | Assigned To | Assigned TS |          │
│               │  Completion TS | Actions                        │
│ † admin only  │                                                  │
│               │  Row actions (admin): Assign · Reset · Edit Time │
│               │  Row actions (artist): Complete (own rows only)  │
└───────────────┴──────────────────────────────────────────────---┘
```

- **Role-scoped grid**: Admin sees every row with full filters; an Artist's grid is hard-filtered server-side to `AssignedToUserID = self` — there is no client-side toggle to widen it (see §dashboard filtering in the API).
- **Import modal**: CSV upload → server returns a duplicate-conflict preview table → per-row choice of Skip / Overwrite / New Version (plus a bulk-apply option) → Confirm commits the batch.
- **Assign modal**: user picker scoped to the file's phase role.
- **Reporting panel**: date-range + group-by (user/week/month/year) selector, chart area, Export to PDF / Excel.
- **Calendar panel**: month view of deadlines per assignment, click-through filters the grid to that day.

## 4. Deliverables in this repo

- `sql/001_schema.sql` — full schema, lookup seed data, `sp_CreateFirstAdmin` bootstrap procedure.
- `app/` — FastAPI + SQLAlchemy boilerplate: models, role-based dashboard filtering, CSV import/versioning logic, the Copy-Verify-Delete transfer service (§2), plus `lookups`/`users`/`assignments` routers the frontend needs (id→name tables, the Assign modal's user picker, and the Complete/Reset actions).
- `.env` / `.env.example` — SQL Server host, port, credentials, DB name, and `CORS_ORIGINS_RAW` (`app/config.py` builds the SQLAlchemy connection URL from these; `JWT_SECRET_KEY` auto-generates and persists to `.env` on first run if left blank).
- `pyproject.toml` — makes `app` an installable package so `import app...` resolves regardless of which file or working directory it's run from (fixes `ModuleNotFoundError: No module named 'app'` when a file under `app/` is run directly instead of via `app.main`).
- `scripts/create_database.py` — connects to `master` with the `.env` credentials, creates the target database if it doesn't exist, then applies `sql/001_schema.sql` (idempotent - safe to re-run).
- `scripts/create_admin.py` — bootstraps the first Admin via `sp_CreateFirstAdmin`, printing a generated username/password once.
- `scripts/reset_password.py <username> <new_password>` — recovery tool if a password is lost; updates the hash directly.
- `setup.ps1` — runs all of the above in order: venv, dependencies, editable install, database, first Admin, frontend build.
- `frontend/` — the Command Center itself: React + Vite + AG-Grid, described in §6.

## 5. First-time setup

1. Fill in `.env` (copy from `.env.example` if starting fresh): `DB_SERVER`, `DB_USER`, `DB_PASSWORD`. Leave `JWT_SECRET_KEY` blank - it self-generates.
2. `.\setup.ps1` — creates `.venv`, installs Python + npm dependencies, creates the database + schema, prints the first Admin's username/password, and builds the frontend (`frontend/dist`).
3. Add at least one row to `PhasePaths` for each phase (`Polish`/`GLB`/`Render`) pointing at its real SMB root - the Assign action returns a clean 400 error until this exists, since there's nowhere to copy files to yet.
4. `.venv\Scripts\python.exe app\main.py` — one process serves both the API and the built UI on `http://localhost:8000`.

## 6. Frontend (Command Center)

React + Vite + `ag-grid-react`, matching the layout in §3.

**Two ways to run it:**

- **Single-process (default, matches step 4 above):** `npm run build` once (done automatically by `setup.ps1`), then `app/main.py` serves `frontend/dist` directly - `GET /` and any client-side route (e.g. `/dashboard` on a hard refresh) return `index.html` via a catch-all route registered *after* all `/api/*` routers, so it never shadows the API. Rebuild (`cd frontend && npm run build`) after changing frontend source - the running backend won't pick up source edits, only the built output.
- **Dev mode (hot reload while editing the frontend):** `cd frontend && npm run dev` runs a separate Vite server on `:5173` that proxies `/api/*` to the backend on `:8000` (`frontend/vite.config.js`), so no CORS setup is needed. Run the backend separately in this mode (`.venv\Scripts\python.exe app\main.py`).

- `src/api/client.js` — thin `fetch` wrapper: stores the JWT in `localStorage`, attaches `Authorization: Bearer`, decodes the token client-side (role/user id) for UI gating only - the server re-checks every permission independently.
- `src/context/AuthContext.jsx` + `src/pages/LoginPage.jsx` — login/logout, protected routes in `App.jsx`.
- `src/pages/DashboardPage.jsx` — loads lookups/users/files, wires filters and row actions together.
- `src/components/FilesGrid.jsx` — the AG-Grid table; renders Phase/Category/Status as names (not raw ids) via `/api/lookups`, and shows Assign/Reset (admin) or Complete (artist, own rows only) per row.
- `src/components/AssignModal.jsx` / `ImportModal.jsx` — the two admin workflows from §3.
- `src/pages/UsersPage.jsx` (`/users`, Admin-only - `AdminRoute` in `App.jsx` redirects non-admins) — the user-management panel: table of users, `CreateUserModal`, `EditUserModal` (role/phase/active), `ResetPasswordModal`. Backed by `POST/PUT /api/admin/users`, `POST /api/admin/users/{id}/reset-password`.
- `src/components/ChangePasswordModal.jsx` — self-service password change for *any* logged-in user (Admin or Artist), opened from the sidebar's "Change Password" button. Calls `POST /api/auth/change-password`, which requires the current password.
- Server-side safety: `PUT /api/admin/users/{id}` refuses to demote or deactivate the last active Admin (`app/routers/users.py::_active_admin_count`) - the panel can't lock everyone out.

### Manual import (filename-only CSVs)

For source CSVs that are just a list of file names with no phase/category/path columns. `ImportModal.jsx` has a "Manual" mode: pick Phase (dropdown), Category/Sub-Category (text input with a datalist of existing names - typing a new name creates it, same as the full-CSV flow's `_lookup_or_create_category`), and a source folder path, then upload a filename-only CSV.

`POST /api/admin/imports/preview` now accepts optional `phase_name`/`category_name`/`sub_category_name`/`source_root_path` form fields alongside the file. When `phase_name` is given, `parse_csv_simple()` (`app/services/csv_import.py`) reads one file name per CSV row and builds `source_path = source_root_path/file_name` plus the shared context for every row - producing the exact same `CsvImportRow` shape the full-CSV path already produces, so `preview_import`/`commit_import` and the conflict-resolution UI need no changes at all. Omitting `phase_name` falls back to the original full-CSV parsing unchanged.

### Moving files between Category/Sub-Category/Phase

`FilesGrid.jsx` has checkbox row selection (Admin only, AG Grid's `rowSelection={{mode: 'multiRow'}}`). Selecting rows surfaces a "Move Selected (N)" button that opens `MoveFilesModal.jsx`, backed by two endpoints in `app/routers/admin.py`:

- `POST /api/admin/files/move-category` — sets `CategoryID`/`SubCategoryID` on the selected files. Pure metadata, no physical folder implication, so always allowed. Picks from the *existing* category/sub-category list (unlike import, this doesn't create new ones).
- `POST /api/admin/files/move-phase` — sets `PhaseID`. This one has a physical implication (`PhasePaths` root differs per phase), so any file with an **active assignment** (its folder already sits under the old phase's root in someone's Pending/InProgress tree) is skipped with a reason rather than force-moved - reset it first, move it, then re-Assign to actually relocate the folder. Also catches the `UNIQUE(FileName, PhaseID)` collision per-file (via a savepoint, same pattern as `commit_import`) if a same-named file already exists in the target phase, reporting it as skipped instead of failing the whole batch.

### Taxonomy management (`/taxonomy`, Admin-only)

Categories are scoped per Phase (see §1) - each phase defines its own category list, and the same name can exist independently under more than one phase. **Phase/Category/Sub-Category are no longer seeded with defaults** - `Polish`/`GLB`/`Render` shipped as example rows during early development but were removed once the schema had a real admin panel to define them explicitly instead (they were being confused with the *Role* concept - `Roles` still has `Polish Artist`/`GLB Artist`/`Render Artist`, which is a separate, unrelated table). A fresh install now starts with an empty `Phases` table; the first thing an Admin does is add phases from `/taxonomy`.

`TaxonomyPage.jsx` renders the full Phase → Category → Sub-Category tree with a file count (and, for phases, a user count) on every node, an Activate/Deactivate toggle, a Delete button, and an inline "+ Add" form at each level:

- `GET /api/admin/taxonomy` - full listing (active *and* inactive, with counts) for this page. Distinct from `GET /api/lookups`, which every other consumer (`FilterBar`, `ImportModal`, `MoveFilesModal`, `CreateUserModal`) reads and which filters to `IsActive=1` only - deactivating something hides it from every dropdown with no per-component change needed, while existing files/users that already reference it keep working (they just render as `#id` if the name lookup misses, an acceptable degrade).
- `POST /api/admin/phases` (create) / `PATCH /api/admin/phases/{id}` `{is_active}` (toggle) / `DELETE /api/admin/phases/{id}` (blocked - reports exactly which of files/users/categories/PhasePaths still reference it).
- `POST /api/admin/categories` `{phase_id, name}` / `PATCH .../{id}` `{is_active}` / `DELETE .../{id}` (blocked if any file uses it).
- `POST /api/admin/subcategories` `{category_id, name}` / `PATCH .../{id}` `{is_active}` / `DELETE .../{id}` (same guard).

Every other Category consumer is phase-aware: `FilterBar.jsx`'s category dropdown filters to the selected phase (and clears category/sub-category when phase changes), `ImportModal.jsx`'s manual-mode category datalist filters the same way, and `MoveFilesModal.jsx` only allows "Move Category" when every selected file shares one phase (categories from different phases aren't interchangeable).

**Migration note:** an already-running database gets migrated automatically - `scripts/create_database.py::apply_schema()` runs a small ordered migration list after confirming the base schema exists. `_migrate_categories_to_phase_scoped` adds `Categories.PhaseID` (refuses to run if any `Files.CategoryID` is already set - splitting a category used across multiple phases needs a human decision this script doesn't attempt). `_migrate_add_is_active` adds `IsActive` to Phases/Categories/SubCategories, defaulting existing rows to active. Just re-run `setup.ps1` (or `python scripts/create_database.py`) to apply either; no manual SQL needed for the common case.

Verified end-to-end against a live SQL Server, both as a single process (`app/main.py` serving `frontend/dist`, including the SPA-fallback and path-traversal guard on the catch-all route) and via the dev proxy: login → dashboard (role-scoped) → CSV import (preview + commit, both full and manual mode) → move-category → move-phase (including the active-assignment skip and the duplicate-name collision skip) → add/deactivate/reactivate/delete Phase/Category/Sub-Category → delete blocked while in use (files, users, categories, or PhasePaths, depending on level) → same category name reused across two phases → Assign (real Copy-Verify-Delete folder move) → Complete (artist) → Reset (admin) → create/edit/deactivate a user → last-admin protection → self-service password change, all through the same HTTP calls the React app makes.

Not built yet: Reports, Calendar, Audit Trail view, and a Settings UI for `PhasePaths` (currently SQL-only - see §5 step 3).

## 7. Future: Backup Strategy (not implemented - revisit before production)

Deliberately deferred - to be designed and configured once the app is ready to go live, not before. Also revisit the data-transfer/migration story at the same time (moving the live database to a new server/environment).

Three-way backup, once a day, once implemented:

1. **SQL-native backup** - a native SQL Server `BACKUP DATABASE` job, restorable directly within SQL Server for fast recovery from corruption or accidental data loss, without needing the other two copies.
2. **NAS / SMB server copy** - the backup file also lands on the internal NAS/SMB share. Folder path TBD when configured.
3. **Cloud copy (OneDrive)** - the backup file also lands in a local folder that's synced by the Windows OneDrive client, so it's mirrored off-site automatically. Folder TBD when configured.

All three run on the same daily schedule. None of this is implemented yet - no backup job, no scripts, no scheduled task exists in this repo today.
