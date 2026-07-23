# Graph Report - .  (2026-07-11)

## Corpus Check
- 44 files · ~30,448 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 603 nodes · 2010 edges · 21 communities (17 shown, 4 thin omitted)
- Extraction: 66% EXTRACTED · 34% INFERRED · 0% AMBIGUOUS · INFERRED: 689 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Database Models|Database Models]]
- [[_COMMUNITY_Dashboard Grid & Assignment UI|Dashboard Grid & Assignment UI]]
- [[_COMMUNITY_App Config & DB Bootstrap|App Config & DB Bootstrap]]
- [[_COMMUNITY_Schema & File Transfer Pipeline Docs|Schema & File Transfer Pipeline Docs]]
- [[_COMMUNITY_Frontend API Client|Frontend API Client]]
- [[_COMMUNITY_Taxonomy Schemas (PhaseCategorySubCategory)|Taxonomy Schemas (Phase/Category/SubCategory)]]
- [[_COMMUNITY_Reports & Audit Trail Schemas|Reports & Audit Trail Schemas]]
- [[_COMMUNITY_CSV Import Schemas|CSV Import Schemas]]
- [[_COMMUNITY_User & Process Type Schemas|User & Process Type Schemas]]
- [[_COMMUNITY_User Management Modals|User Management Modals]]
- [[_COMMUNITY_Frontend Dependencies|Frontend Dependencies]]
- [[_COMMUNITY_Production Pipeline Overview Docs|Production Pipeline Overview Docs]]
- [[_COMMUNITY_Lint Config|Lint Config]]
- [[_COMMUNITY_Vite Build Plugin (Oxc)|Vite Build Plugin (Oxc)]]
- [[_COMMUNITY_Vite Build Plugin (SWC)|Vite Build Plugin (SWC)]]
- [[_COMMUNITY_Project Root|Project Root]]
- [[_COMMUNITY_App Branding|App Branding]]

## God Nodes (most connected - your core abstractions)
1. `User` - 78 edges
2. `request()` - 51 edges
3. `FileRecord` - 50 edges
4. `ProcessType` - 45 edges
5. `TaskAssignment` - 38 edges
6. `FileProcessStatus` - 37 edges
7. `SubCategory` - 35 edges
8. `Phase` - 34 edges
9. `FileStatus` - 34 edges
10. `AuditTrail` - 29 edges

## Surprising Connections (you probably didn't know these)
- `Automatic Schema Migration` --implements--> `apply_schema()`  [EXTRACTED]
  planning.md → scripts/create_database.py
- `apply_schema()` --calls--> `_migrate_categories_to_phase_scoped()`  [EXTRACTED]
  scripts/create_database.py → planning.md
- `Manual Import Mode (filename-only CSV)` --implements--> `parse_csv_simple()`  [EXTRACTED]
  planning.md → app/services/csv_import.py
- `parse_csv_simple()` --shares_data_with--> `CsvImportRow`  [EXTRACTED]
  app/services/csv_import.py → planning.md
- `preview_import()` --shares_data_with--> `CsvImportRow`  [EXTRACTED]
  app/services/csv_import.py → planning.md

## Import Cycles
- None detected.

## Communities (21 total, 4 thin omitted)

### Community 0 - "Database Models"
Cohesion: 0.10
Nodes (82): AuditTrail, FileProcessStatus, FileRecord, FileStatus, FileTransferLog, FileVersion, TaskAssignment, User (+74 more)

### Community 1 - "Dashboard Grid & Assignment UI"
Cohesion: 0.05
Nodes (46): AssignModal(), FailAssignmentModal(), FileHistoryModal(), FilesGrid(), FilterBar(), SearchBox(), Sidebar(), AuthContext (+38 more)

### Community 2 - "App Config & DB Bootstrap"
Cohesion: 0.05
Nodes (48): _ensure_jwt_secret(), Connects to the 'master' system database - used only to create db_name if it doe, Generates a JWT secret on first run if .env left it blank, and writes it     bac, Settings, get_db(), Session, User, User (+40 more)

### Community 3 - "Schema & File Transfer Pipeline Docs"
Cohesion: 0.06
Nodes (58): Connection, app/ (FastAPI + SQLAlchemy backend), AuditTrail (table), Categories (table), Copy-Verify-Delete Pipeline, Files (table), FileStatuses (table), FileTransferLog (table) (+50 more)

### Community 4 - "Frontend API Client"
Cohesion: 0.07
Nodes (55): adminResetPassword(), assignFile(), browseFolders(), changePassword(), commitImport(), completeAssignment(), createCategory(), createPhase() (+47 more)

### Community 5 - "Taxonomy Schemas (Phase/Category/SubCategory)"
Cohesion: 0.16
Nodes (49): Category, Phase, PhasePath, SubCategory, Session, User, Session, User (+41 more)

### Community 6 - "Reports & Audit Trail Schemas"
Cohesion: 0.15
Nodes (43): Session, User, Session, User, Session, User, AuditTrailEntryOut, AuditTrailFilterParams (+35 more)

### Community 7 - "CSV Import Schemas"
Cohesion: 0.14
Nodes (33): CsvImportCommitRequest, Session, User, CsvImportCommitRequest, CsvImportConflict, CsvImportPreview, CsvImportRow, DuplicateResolution (+25 more)

### Community 8 - "User & Process Type Schemas"
Cohesion: 0.28
Nodes (31): ImportBatch, ProcessType, Role, WorkerProcessPath, Session, User, CreateUserRequest, ResetPasswordRequest (+23 more)

### Community 9 - "User Management Modals"
Cohesion: 0.11
Nodes (11): ComboSelect(), CreateUserModal(), EditUserModal(), FolderBrowserModal(), Modal(), RoleCheckboxGroup(), EMPTY_LOOKUPS, UsersPage() (+3 more)

### Community 10 - "Frontend Dependencies"
Cohesion: 0.09
Nodes (22): dependencies, ag-grid-community, ag-grid-react, react, react-dom, react-router-dom, recharts, devDependencies (+14 more)

### Community 11 - "Production Pipeline Overview Docs"
Cohesion: 0.11
Nodes (23): Admin Command Center, Admin Role, AG-Grid (Frontend), Assignment Stage (Admin assigns task -> lock check -> move folder), Completion Stage (Complete -> Completion_TS -> Status update -> Next phase), Copy-Verify-Delete Mechanism, Corrections (Admin reset for accidental completions), Dashboard (Grid with filters for Phase/Category/Sub-Category) (+15 more)

### Community 12 - "Lint Config"
Cohesion: 0.33
Nodes (5): plugins, rules, react/only-export-components, react/rules-of-hooks, $schema

## Ambiguous Edges - Review These
- `parse_csv_simple()` → `_lookup_or_create_category()`  [AMBIGUOUS]
  planning.md · relation: conceptually_related_to

## Knowledge Gaps
- **69 isolated node(s):** `Python (FastAPI)`, `FastAPI`, `AG-Grid (Frontend)`, `Settings Table (Role_Root_Paths)`, `Reporting (SQL Views -> Export to PDF/Excel)` (+64 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `parse_csv_simple()` and `_lookup_or_create_category()`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Frontend (Command Center) - React + Vite + AG-Grid` connect `Dashboard Grid & Assignment UI` to `App Config & DB Bootstrap`, `Schema & File Transfer Pipeline Docs`, `Frontend API Client`, `CSV Import Schemas`?**
  _High betweenness centrality (0.167) - this node is a cross-community bridge._
- **Why does `User` connect `Database Models` to `App Config & DB Bootstrap`, `Taxonomy Schemas (Phase/Category/SubCategory)`, `Reports & Audit Trail Schemas`, `CSV Import Schemas`, `User & Process Type Schemas`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `app/ (FastAPI + SQLAlchemy backend)` connect `Schema & File Transfer Pipeline Docs` to `User & Process Type Schemas`, `CSV Import Schemas`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 61 inferred relationships involving `User` (e.g. with `Session` and `User`) actually correct?**
  _`User` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `FileRecord` (e.g. with `Session` and `User`) actually correct?**
  _`FileRecord` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 34 inferred relationships involving `ProcessType` (e.g. with `Session` and `User`) actually correct?**
  _`ProcessType` has 34 INFERRED edges - model-reasoned connections that need verification._