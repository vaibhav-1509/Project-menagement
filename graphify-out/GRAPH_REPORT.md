# Graph Report - Project menagement  (2026-07-23)

## Corpus Check
- 417 files · ~2,544,603 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 655 nodes · 1933 edges · 29 communities (25 shown, 4 thin omitted)
- Extraction: 70% EXTRACTED · 30% INFERRED · 0% AMBIGUOUS · INFERRED: 580 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c47f4393`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Database Models
- Dashboard Grid & Assignment UI
- App Config & DB Bootstrap
- Schema & File Transfer Pipeline Docs
- Frontend API Client
- Taxonomy Schemas (Phase/Category/SubCategory)
- Reports & Audit Trail Schemas
- CSV Import Schemas
- User & Process Type Schemas
- User Management Modals
- Frontend Dependencies
- Production Pipeline Overview Docs
- Lint Config
- Vite Build Plugin (Oxc)
- Vite Build Plugin (SWC)
- Project Root
- App Branding
- schemas.py
- Frontend (Command Center) - React + Vite + AG-Grid
- App.jsx
- downloadFile
- Settings
- DashboardPage.jsx

## God Nodes (most connected - your core abstractions)
1. `request()` - 74 edges
2. `User` - 71 edges
3. `ProcessType` - 45 edges
4. `FileRecord` - 43 edges
5. `FileStatus` - 34 edges
6. `TaskAssignment` - 31 edges
7. `FileProcessStatus` - 30 edges
8. `Category` - 28 edges
9. `SubCategory` - 28 edges
10. `Phase` - 27 edges

## Surprising Connections (you probably didn't know these)
- `Manual Import Mode (filename-only CSV)` --implements--> `parse_csv_simple()`  [EXTRACTED]
  planning.md → app/services/csv_import.py
- `Automatic Schema Migration` --implements--> `apply_schema()`  [EXTRACTED]
  planning.md → scripts/create_database.py
- `apply_schema()` --calls--> `_migrate_categories_to_phase_scoped()`  [EXTRACTED]
  scripts/create_database.py → planning.md
- `apply_schema()` --calls--> `_migrate_add_is_active()`  [EXTRACTED]
  scripts/create_database.py → planning.md
- `parse_csv_simple()` --shares_data_with--> `CsvImportRow`  [EXTRACTED]
  app/services/csv_import.py → planning.md

## Import Cycles
- None detected.

## Communities (29 total, 4 thin omitted)

### Community 0 - "Database Models"
Cohesion: 0.12
Nodes (63): FileProcessStatus, FileRecord, FileStatus, FileTransferLog, FileVersion, ProcessType, TaskAssignment, Session (+55 more)

### Community 1 - "Dashboard Grid & Assignment UI"
Cohesion: 0.06
Nodes (29): FileHistoryModal(), FilesGrid(), SearchBox(), Sidebar(), AuthContext, AuthProvider(), useAuth(), index.html (App Entry) (+21 more)

### Community 2 - "App Config & DB Bootstrap"
Cohesion: 0.07
Nodes (47): get_db(), User, Session, User, Session, User, User, AuditTrailEntryOut (+39 more)

### Community 3 - "Schema & File Transfer Pipeline Docs"
Cohesion: 0.10
Nodes (34): Connection, Automatic Schema Migration, _migrate_categories_to_phase_scoped(), apply_schema(), _column_exists(), create_database_if_missing(), _index_exists(), _migrate_add_audit_trail_indexes() (+26 more)

### Community 4 - "Frontend API Client"
Cohesion: 0.05
Nodes (70): addMyLeave(), addUserLeave(), adminResetPassword(), approveFile(), assignBulk(), assignFile(), browseFolders(), cancelMyLeave() (+62 more)

### Community 5 - "Taxonomy Schemas (Phase/Category/SubCategory)"
Cohesion: 0.16
Nodes (49): Category, Phase, PhasePath, SubCategory, Session, User, Session, User (+41 more)

### Community 6 - "Reports & Audit Trail Schemas"
Cohesion: 0.27
Nodes (19): Session, User, BucketCountOut, Everything needed to render one custom [startDate, endDate] range:     a daily, ReportsCompletionsOut, TaxonomyProgressItemOut, TaxonomyProgressOut, date_cls (+11 more)

### Community 7 - "CSV Import Schemas"
Cohesion: 0.15
Nodes (31): CsvImportCommitRequest, Session, User, CsvImportCommitRequest, CsvImportConflict, CsvImportPreview, CsvImportRow, DuplicateResolution (+23 more)

### Community 8 - "User & Process Type Schemas"
Cohesion: 0.28
Nodes (31): AuditTrail, ImportBatch, Role, WorkerProcessPath, Session, User, CreateUserRequest, ResetPasswordRequest (+23 more)

### Community 9 - "User Management Modals"
Cohesion: 0.11
Nodes (10): ComboSelect(), CreateUserModal(), EditUserModal(), FolderBrowserModal(), Modal(), RoleCheckboxGroup(), EMPTY_LOOKUPS, POST /api/auth/change-password (+2 more)

### Community 10 - "Frontend Dependencies"
Cohesion: 0.09
Nodes (22): dependencies, ag-grid-community, ag-grid-react, react, react-dom, react-router-dom, recharts, devDependencies (+14 more)

### Community 11 - "Production Pipeline Overview Docs"
Cohesion: 0.11
Nodes (23): Admin Command Center, Admin Role, AG-Grid (Frontend), Assignment Stage (Admin assigns task -> lock check -> move folder), Completion Stage (Complete -> Completion_TS -> Status update -> Next phase), Copy-Verify-Delete Mechanism, Corrections (Admin reset for accidental completions), Dashboard (Grid with filters for Phase/Category/Sub-Category) (+15 more)

### Community 12 - "Lint Config"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

### Community 21 - "schemas.py"
Cohesion: 0.09
Nodes (47): assign(), bulk_assign(), delete_file(), move_category(), move_phase(), Assign multiple files to the same worker for the same process type.     Each fi, Reclassifies selected files' Category/Sub-Category. Pure metadata - no     phys, Reclassifies selected files' Phase. Unlike Category/Sub-Category this has     a (+39 more)

### Community 22 - "Frontend (Command Center) - React + Vite + AG-Grid"
Cohesion: 0.07
Nodes (37): Oxlint, React, React Compiler, Vite, app/ (FastAPI + SQLAlchemy backend), AuditTrail (table), Categories (table), Command Center UI Layout (+29 more)

### Community 23 - "App.jsx"
Cohesion: 0.12
Nodes (11): AuditTrailPage, BrowseFilesPage, CalendarPage, DashboardPage, LoginPage, ProcessTypesPage, ProfilePage, ReportsPage (+3 more)

### Community 24 - "downloadFile"
Cohesion: 0.27
Nodes (10): changePassword(), downloadFile(), _exportQueryString(), exportReportExcel(), exportReportPdf(), getToken(), login(), logout() (+2 more)

### Community 25 - "Settings"
Cohesion: 0.28
Nodes (5): _ensure_jwt_secret(), Connects to the 'master' system database - used only to create db_name if it doe, Generates a JWT secret on first run if .env left it blank, and writes it     bac, Settings, BaseSettings

### Community 26 - "DashboardPage.jsx"
Cohesion: 0.47
Nodes (3): AssignSelectedModal(), workerLabel(), EMPTY_LOOKUPS

## Ambiguous Edges - Review These
- `parse_csv_simple()` → `_lookup_or_create_category()`  [AMBIGUOUS]
  planning.md · relation: conceptually_related_to

## Knowledge Gaps
- **79 isolated node(s):** `LoginPage`, `DashboardPage`, `BrowseFilesPage`, `UsersPage`, `TaxonomyPage` (+74 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `parse_csv_simple()` and `_lookup_or_create_category()`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Frontend (Command Center) - React + Vite + AG-Grid` connect `Frontend (Command Center) - React + Vite + AG-Grid` to `Dashboard Grid & Assignment UI`, `App Config & DB Bootstrap`?**
  _High betweenness centrality (0.182) - this node is a cross-community bridge._
- **Why does `User` connect `App Config & DB Bootstrap` to `Database Models`, `Taxonomy Schemas (Phase/Category/SubCategory)`, `Reports & Audit Trail Schemas`, `CSV Import Schemas`, `User & Process Type Schemas`, `schemas.py`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `Move Files (Category/Sub-Category/Phase)` connect `Frontend (Command Center) - React + Vite + AG-Grid` to `User Management Modals`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 55 inferred relationships involving `User` (e.g. with `Session` and `User`) actually correct?**
  _`User` has 55 INFERRED edges - model-reasoned connections that need verification._
- **Are the 34 inferred relationships involving `ProcessType` (e.g. with `Session` and `User`) actually correct?**
  _`ProcessType` has 34 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `FileRecord` (e.g. with `Session` and `User`) actually correct?**
  _`FileRecord` has 32 INFERRED edges - model-reasoned connections that need verification._