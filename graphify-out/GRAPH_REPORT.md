# Graph Report - .  (2026-07-09)

## Corpus Check
- 55 files · ~17,714 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 411 nodes · 1150 edges · 21 communities (17 shown, 4 thin omitted)
- Extraction: 71% EXTRACTED · 29% INFERRED · 0% AMBIGUOUS · INFERRED: 338 edges (avg confidence: 0.52)
- Token cost: 0 input · 124,619 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Frontend UI Components|Frontend UI Components]]
- [[_COMMUNITY_Schema & Setup Docs|Schema & Setup Docs]]
- [[_COMMUNITY_App Config & Auth Session|App Config & Auth Session]]
- [[_COMMUNITY_File Assignment & Transfer Pipeline|File Assignment & Transfer Pipeline]]
- [[_COMMUNITY_Taxonomy Management|Taxonomy Management]]
- [[_COMMUNITY_Frontend API Client|Frontend API Client]]
- [[_COMMUNITY_CSV Import|CSV Import]]
- [[_COMMUNITY_User & Role Management|User & Role Management]]
- [[_COMMUNITY_Original Project Plan Doc|Original Project Plan Doc]]
- [[_COMMUNITY_Frontend Dependencies|Frontend Dependencies]]
- [[_COMMUNITY_Filesystem Browser|Filesystem Browser]]
- [[_COMMUNITY_Planning Doc AuthImport Notes|Planning Doc: Auth/Import Notes]]
- [[_COMMUNITY_Lint Config|Lint Config]]
- [[_COMMUNITY_README Oxc Tooling|README: Oxc Tooling]]
- [[_COMMUNITY_README SWC Tooling|README: SWC Tooling]]
- [[_COMMUNITY_Root Package Marker|Root Package Marker]]
- [[_COMMUNITY_Favicon Icon|Favicon Icon]]

## God Nodes (most connected - your core abstractions)
1. `User` - 54 edges
2. `FileRecord` - 33 edges
3. `request()` - 30 edges
4. `SubCategory` - 25 edges
5. `User` - 25 edges
6. `Session` - 25 edges
7. `Phase` - 24 edges
8. `TaskAssignment` - 21 edges
9. `Category` - 19 edges
10. `FileStatus` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Manual Import Mode (filename-only CSV)` --implements--> `parse_csv_simple()`  [EXTRACTED]
  planning.md → app/services/csv_import.py
- `Automatic Schema Migration` --implements--> `apply_schema()`  [EXTRACTED]
  planning.md → scripts/create_database.py
- `apply_schema()` --calls--> `_migrate_categories_to_phase_scoped()`  [EXTRACTED]
  scripts/create_database.py → planning.md
- `parse_csv_simple()` --shares_data_with--> `CsvImportRow`  [EXTRACTED]
  app/services/csv_import.py → planning.md
- `preview_import()` --shares_data_with--> `CsvImportRow`  [EXTRACTED]
  app/services/csv_import.py → planning.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Copy-Verify-Delete Transfer Pipeline** — planning_copy_verify_delete, planning_filetransferlog, planning_taskassignments, planning_files, planning_fileversions [INFERRED 0.85]
- **Move Files Between Category/Phase Flow** — components_movefilesmodal, planning_move_files, planning_files, planning_categories, planning_phases [INFERRED 0.80]
- **JWT Authentication & Session Flow** — planning_jwt_auth, api_client, context_authcontext, pages_loginpage, app_config [INFERRED 0.80]

## Communities (21 total, 4 thin omitted)

### Community 0 - "Frontend UI Components"
Cohesion: 0.08
Nodes (31): AssignModal(), ChangePasswordModal(), ComboSelect(), CreateUserModal(), EditUserModal(), FilesGrid(), FilterBar(), FolderBrowserModal() (+23 more)

### Community 1 - "Schema & Setup Docs"
Cohesion: 0.06
Nodes (47): Oxlint, React, React Compiler, Vite, app/ (FastAPI + SQLAlchemy backend), AuditTrail (table), Categories (table), Copy-Verify-Delete Pipeline (+39 more)

### Community 2 - "App Config & Auth Session"
Cohesion: 0.07
Nodes (34): _ensure_jwt_secret(), Connects to the 'master' system database - used only to create db_name if it doe, Generates a JWT secret on first run if .env left it blank, and writes it     bac, Settings, get_db(), Session, User, Session (+26 more)

### Community 3 - "File Assignment & Transfer Pipeline"
Cohesion: 0.18
Nodes (40): AuditTrail, FileRecord, FileStatus, FileTransferLog, FileVersion, PhasePath, SubCategory, TaskAssignment (+32 more)

### Community 4 - "Taxonomy Management"
Cohesion: 0.21
Nodes (38): Category, Phase, Session, User, Session, User, CategoryAdminOut, CategoryLookupItem (+30 more)

### Community 5 - "Frontend API Client"
Cohesion: 0.10
Nodes (34): adminResetPassword(), assignFile(), browseFolders(), changePassword(), commitImport(), completeAssignment(), createCategory(), createPhase() (+26 more)

### Community 6 - "CSV Import"
Cohesion: 0.16
Nodes (31): ImportBatch, CsvImportCommitRequest, Session, User, CsvImportCommitRequest, CsvImportConflict, CsvImportPreview, CsvImportRow (+23 more)

### Community 7 - "User & Role Management"
Cohesion: 0.22
Nodes (24): Role, Session, User, CreateUserRequest, ResetPasswordRequest, UpdateUserRequest, UserOut, hash_password() (+16 more)

### Community 8 - "Original Project Plan Doc"
Cohesion: 0.11
Nodes (23): Admin Command Center, Admin Role, AG-Grid (Frontend), Assignment Stage (Admin assigns task -> lock check -> move folder), Completion Stage (Complete -> Completion_TS -> Status update -> Next phase), Copy-Verify-Delete Mechanism, Corrections (Admin reset for accidental completions), Dashboard (Grid with filters for Phase/Category/Sub-Category) (+15 more)

### Community 9 - "Frontend Dependencies"
Cohesion: 0.09
Nodes (21): dependencies, ag-grid-community, ag-grid-react, react, react-dom, react-router-dom, devDependencies, oxlint (+13 more)

### Community 10 - "Filesystem Browser"
Cohesion: 0.39
Nodes (8): User, browse_folders(), BrowseFoldersOut, FolderEntry, _list_shares(), _local_drive_roots(), A bare `\\host` isn't itself an openable directory on Windows - you can     only, Lists subfolders under `path` so an admin can pick a source folder by     clicki

### Community 11 - "Planning Doc: Auth/Import Notes"
Cohesion: 0.29
Nodes (7): Command Center UI Layout, Import Modal (CSV import + conflict resolution), JWT Authentication, Manual Import Mode (filename-only CSV), Role-scoped Grid (server-side RBAC filtering), python-jose[cryptography], python-multipart

### Community 12 - "Lint Config"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

## Ambiguous Edges - Review These
- `parse_csv_simple()` → `_lookup_or_create_category()`  [AMBIGUOUS]
  planning.md · relation: conceptually_related_to

## Knowledge Gaps
- **58 isolated node(s):** `Python (FastAPI)`, `FastAPI`, `AG-Grid (Frontend)`, `Settings Table (Role_Root_Paths)`, `Reporting (SQL Views -> Export to PDF/Excel)` (+53 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `parse_csv_simple()` and `_lookup_or_create_category()`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Frontend (Command Center) - React + Vite + AG-Grid` connect `Schema & Setup Docs` to `Frontend UI Components`, `App Config & Auth Session`, `Planning Doc: Auth/Import Notes`, `Frontend API Client`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Why does `User` connect `File Assignment & Transfer Pipeline` to `App Config & Auth Session`, `Taxonomy Management`, `CSV Import`, `User & Role Management`, `Filesystem Browser`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Why does `app/ (FastAPI + SQLAlchemy backend)` connect `Schema & Setup Docs` to `CSV Import`, `User & Role Management`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Are the 41 inferred relationships involving `User` (e.g. with `Session` and `User`) actually correct?**
  _`User` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `FileRecord` (e.g. with `Session` and `User`) actually correct?**
  _`FileRecord` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `SubCategory` (e.g. with `Session` and `User`) actually correct?**
  _`SubCategory` has 17 INFERRED edges - model-reasoned connections that need verification._