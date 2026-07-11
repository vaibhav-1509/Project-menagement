"""One-time setup: creates the target SQL Server database (if missing) and
applies sql/001_schema.sql. Reads connection details from .env via app.config.

Usage:
    python scripts/create_database.py
"""

import re
import sys
from pathlib import Path

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # allow `import app.config`
from app.config import settings  # noqa: E402

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "001_schema.sql"


def _raw_connect(database: str) -> pyodbc.Connection:
    # CREATE DATABASE and running a schema batch-by-batch both need autocommit -
    # they can't run inside a SQLAlchemy-managed transaction.
    conn_str = (
        f"DRIVER={{{settings.db_driver}}};"
        f"SERVER={settings.db_server},{settings.db_port};"
        f"DATABASE={database};"
        f"UID={settings.db_user};"
        f"PWD={settings.db_password};"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, autocommit=True)


def create_database_if_missing() -> None:
    conn = _raw_connect("master")
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = '{settings.db_name}') "
            f"CREATE DATABASE [{settings.db_name}]"
        )
        print(f"Database '{settings.db_name}' ready.")
    finally:
        conn.close()


def _split_batches(sql_text: str) -> list[str]:
    """Splits on a standalone GO line, the way sqlcmd/SSMS do - but ignores GO
    tokens that fall inside a /* ... */ comment, so an example snippet in a
    comment (e.g. "CREATE DATABASE x; GO") can't be mistaken for a real batch
    separator and split a comment block in half."""
    batches = []
    current: list[str] = []
    in_block_comment = False

    for line in sql_text.split("\n"):
        if in_block_comment:
            current.append(line)
            if "*/" in line:
                in_block_comment = False
            continue

        if not in_block_comment and re.match(r"(?i)^\s*GO\s*$", line):
            batches.append("\n".join(current))
            current = []
            continue

        current.append(line)
        if "/*" in line and line.rfind("/*") > line.rfind("*/"):
            in_block_comment = True

    batches.append("\n".join(current))
    return batches


def _schema_already_applied(cursor) -> bool:
    cursor.execute("SELECT OBJECT_ID('dbo.Roles', 'U')")
    return cursor.fetchone()[0] is not None


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ? AND COLUMN_NAME = ?", table, column
    )
    return cursor.fetchone() is not None


def _migrate_categories_to_phase_scoped(cursor) -> None:
    """Categories used to be global (UNIQUE on name alone); now each one belongs
    to exactly one Phase. Safe to auto-run only while no Files reference a
    Category yet - once real data exists, a category used across multiple
    phases would need to be split and its files repointed, which this does not
    attempt. Runs as part of apply_schema() so `setup.ps1` stays the one command
    that brings an existing database up to date, same as any other step here."""
    cursor.execute("SELECT COUNT(*) FROM Files WHERE CategoryID IS NOT NULL")
    if cursor.fetchone()[0] > 0:
        raise RuntimeError(
            "Cannot auto-migrate Categories to be phase-scoped: Files already reference "
            "a Category. This migration assumes an empty taxonomy. Back up the database "
            "and migrate Categories/SubCategories/Files by hand before re-running."
        )

    print("Migrating Categories to be phase-scoped (no files reference one yet, so this is safe)...")
    cursor.execute("DELETE FROM SubCategories")
    cursor.execute("DELETE FROM Categories")
    cursor.execute("ALTER TABLE Categories ADD PhaseID INT NULL")
    cursor.execute(
        "ALTER TABLE Categories ADD CONSTRAINT FK_Categories_Phase FOREIGN KEY (PhaseID) REFERENCES Phases(PhaseID)"
    )
    cursor.execute(
        """
        DECLARE @constraintName NVARCHAR(200);
        SELECT @constraintName = kc.name
        FROM sys.key_constraints kc
        JOIN sys.tables t ON kc.parent_object_id = t.object_id
        WHERE t.name = 'Categories' AND kc.type = 'UQ';
        IF @constraintName IS NOT NULL
            EXEC('ALTER TABLE Categories DROP CONSTRAINT [' + @constraintName + ']');
        """
    )
    cursor.execute("ALTER TABLE Categories ALTER COLUMN PhaseID INT NOT NULL")
    cursor.execute("ALTER TABLE Categories ADD CONSTRAINT UQ_Category_Name_Phase UNIQUE (PhaseID, CategoryName)")
    print("Categories migrated - each one now belongs to exactly one phase.")


def _migrate_add_is_active(cursor) -> None:
    """Adds IsActive to Phases/Categories/SubCategories so the taxonomy admin
    panel can deactivate one (hide it from new selections) without deleting it
    and breaking existing FK references."""
    print("Adding IsActive to Phases/Categories/SubCategories...")
    for table in ("Phases", "Categories", "SubCategories"):
        if not _column_exists(cursor, table, "IsActive"):
            cursor.execute(f"ALTER TABLE {table} ADD IsActive BIT NOT NULL DEFAULT 1")
    print("IsActive added - existing rows default to active.")


def _table_exists(cursor, table: str) -> bool:
    cursor.execute("SELECT OBJECT_ID(?, 'U')", table)
    return cursor.fetchone()[0] is not None


def _migrate_add_failed_status(cursor) -> None:
    cursor.execute("SELECT 1 FROM FileStatuses WHERE StatusName = 'Failed'")
    if cursor.fetchone() is None:
        print("Adding 'Failed' file status...")
        cursor.execute("INSERT INTO FileStatuses (StatusName) VALUES ('Failed')")


def _migrate_add_revoked_status(cursor) -> None:
    """'Revoked' marks an assignment as an admin data-entry mistake (wrong
    file/wrong worker) rather than real work that was later walked back -
    Calendar/Reports exclude it from history, unlike a legitimate Reset."""
    cursor.execute("SELECT 1 FROM FileStatuses WHERE StatusName = 'Revoked'")
    if cursor.fetchone() is None:
        print("Adding 'Revoked' file status...")
        cursor.execute("INSERT INTO FileStatuses (StatusName) VALUES ('Revoked')")


def _migrate_create_process_types(cursor) -> None:
    print("Creating ProcessTypes (Polish/GLB/Render pipeline stages)...")
    cursor.execute(
        """
        CREATE TABLE ProcessTypes (
            ProcessTypeID   INT IDENTITY(1,1) PRIMARY KEY,
            ProcessTypeName NVARCHAR(50) NOT NULL UNIQUE,
            SortOrder       INT NOT NULL UNIQUE,
            IsActive        BIT NOT NULL DEFAULT 1
        )
        """
    )
    cursor.execute(
        "INSERT INTO ProcessTypes (ProcessTypeName, SortOrder) VALUES ('Polish', 10), ('GLB', 20), ('Render', 30)"
    )
    print("ProcessTypes created and seeded.")


def _migrate_create_worker_process_paths(cursor) -> None:
    print("Creating WorkerProcessPaths (per-worker Pending/Complete folders per stage)...")
    cursor.execute(
        """
        CREATE TABLE WorkerProcessPaths (
            WorkerProcessPathID INT IDENTITY(1,1) PRIMARY KEY,
            UserID          INT NOT NULL FOREIGN KEY REFERENCES Users(UserID),
            ProcessTypeID   INT NOT NULL FOREIGN KEY REFERENCES ProcessTypes(ProcessTypeID),
            PendingPath     NVARCHAR(500) NOT NULL,
            CompletePath    NVARCHAR(500) NOT NULL,
            IsActive        BIT NOT NULL DEFAULT 1,
            CONSTRAINT UQ_WorkerProcessPaths UNIQUE (UserID, ProcessTypeID)
        )
        """
    )
    cursor.execute("CREATE INDEX IX_WorkerProcessPaths_ProcessType ON WorkerProcessPaths(ProcessTypeID, IsActive)")
    print("WorkerProcessPaths created - empty until an admin configures a worker's folders.")


def _migrate_add_files_current_path(cursor) -> None:
    print("Adding Files.CurrentPath (tracks where a file's folder physically sits right now)...")
    cursor.execute("ALTER TABLE Files ADD CurrentPath NVARCHAR(500) NULL")
    # Recover the real current location for anything already transferred under the
    # old single-stage assign flow, via FileTransferLog's per-attempt DestPath;
    # fall back to the original import path for files never touched.
    cursor.execute(
        """
        UPDATE f
        SET f.CurrentPath = COALESCE(
            (SELECT TOP 1 ftl.DestPath FROM FileTransferLog ftl
             WHERE ftl.FileID = f.FileID AND ftl.Step = 'Copy' AND ftl.Status = 'Success'
             ORDER BY ftl.Timestamp DESC),
            (SELECT fv.SourcePath FROM FileVersions fv WHERE fv.VersionID = f.CurrentVersionID)
        )
        FROM Files f
        """
    )
    print("Files.CurrentPath added and backfilled.")


def _migrate_add_process_type_to_task_assignments(cursor) -> None:
    print("Adding ProcessTypeID/FailureReason/SourcePath/DestPath to TaskAssignments...")
    cursor.execute("ALTER TABLE TaskAssignments ADD ProcessTypeID INT NULL")
    # Legacy assignments predate process types - anchor them to the first stage
    # (Polish) rather than leave NULL, which would let the filtered unique index
    # admit multiple "active" rows per file (NULL <> NULL under uniqueness).
    cursor.execute("UPDATE TaskAssignments SET ProcessTypeID = (SELECT MIN(ProcessTypeID) FROM ProcessTypes)")
    cursor.execute(
        "ALTER TABLE TaskAssignments ADD CONSTRAINT FK_TaskAssignments_ProcessType "
        "FOREIGN KEY (ProcessTypeID) REFERENCES ProcessTypes(ProcessTypeID)"
    )
    cursor.execute("ALTER TABLE TaskAssignments ALTER COLUMN ProcessTypeID INT NOT NULL")
    cursor.execute("ALTER TABLE TaskAssignments ADD FailureReason NVARCHAR(1000) NULL")
    cursor.execute("ALTER TABLE TaskAssignments ADD SourcePath NVARCHAR(500) NULL")
    cursor.execute("ALTER TABLE TaskAssignments ADD DestPath NVARCHAR(500) NULL")
    cursor.execute("DROP INDEX UQ_TaskAssignments_ActivePerFile ON TaskAssignments")
    cursor.execute(
        "CREATE UNIQUE INDEX UQ_TaskAssignments_ActivePerFileProcessType "
        "ON TaskAssignments(FileID, ProcessTypeID) WHERE IsActive = 1"
    )
    print("TaskAssignments migrated - now the full per-(file, process type) attempt history.")


def _migrate_create_file_process_status(cursor) -> None:
    print("Creating FileProcessStatus (current Polish/GLB/Render status per file)...")
    cursor.execute(
        """
        CREATE TABLE FileProcessStatus (
            FileProcessStatusID INT IDENTITY(1,1) PRIMARY KEY,
            FileID              INT NOT NULL FOREIGN KEY REFERENCES Files(FileID),
            ProcessTypeID       INT NOT NULL FOREIGN KEY REFERENCES ProcessTypes(ProcessTypeID),
            StatusID            INT NOT NULL FOREIGN KEY REFERENCES FileStatuses(StatusID),
            AssignedToUserID    INT NULL FOREIGN KEY REFERENCES Users(UserID),
            ActiveAssignmentID  INT NULL FOREIGN KEY REFERENCES TaskAssignments(AssignmentID),
            LastFailureReason   NVARCHAR(1000) NULL,
            StartedTS           DATETIME2 NULL,
            CompletionTS        DATETIME2 NULL,
            UpdatedAt           DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
            CONSTRAINT UQ_FileProcessStatus_File_ProcessType UNIQUE (FileID, ProcessTypeID)
        )
        """
    )
    cursor.execute("CREATE INDEX IX_FileProcessStatus_ProcessType_Status ON FileProcessStatus(ProcessTypeID, StatusID)")
    cursor.execute("CREATE INDEX IX_FileProcessStatus_AssignedTo ON FileProcessStatus(AssignedToUserID)")

    # Backfill one row per (existing File x active ProcessType). Only the lowest
    # SortOrder stage (Polish) can inherit any state from the old single-status
    # model - every later stage starts Pending, since the old schema had no
    # process-type dimension to recover one from.
    cursor.execute("SELECT ProcessTypeID FROM ProcessTypes WHERE IsActive = 1 ORDER BY SortOrder")
    process_type_ids = [row[0] for row in cursor.fetchall()]
    if not process_type_ids:
        return
    first_process_type_id = process_type_ids[0]
    pending_status_id = _status_id(cursor, "Pending")
    complete_status_id = _status_id(cursor, "Complete")

    cursor.execute("SELECT FileID FROM Files")
    file_ids = [row[0] for row in cursor.fetchall()]
    for file_id in file_ids:
        for process_type_id in process_type_ids:
            if process_type_id != first_process_type_id:
                cursor.execute(
                    "INSERT INTO FileProcessStatus (FileID, ProcessTypeID, StatusID) VALUES (?, ?, ?)",
                    file_id,
                    process_type_id,
                    pending_status_id,
                )
                continue

            cursor.execute(
                "SELECT AssignmentID, StatusID, AssignedToUserID, AssignedTS FROM TaskAssignments "
                "WHERE FileID = ? AND IsActive = 1",
                file_id,
            )
            active = cursor.fetchone()
            if active is not None:
                assignment_id, status_id, assigned_to_user_id, assigned_ts = active
                cursor.execute(
                    "INSERT INTO FileProcessStatus "
                    "(FileID, ProcessTypeID, StatusID, AssignedToUserID, ActiveAssignmentID, StartedTS) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    file_id,
                    process_type_id,
                    status_id,
                    assigned_to_user_id,
                    assignment_id,
                    assigned_ts,
                )
                continue

            cursor.execute("SELECT StatusID, UpdatedAt FROM Files WHERE FileID = ?", file_id)
            file_status_id, updated_at = cursor.fetchone()
            if file_status_id == complete_status_id:
                cursor.execute(
                    "INSERT INTO FileProcessStatus (FileID, ProcessTypeID, StatusID, CompletionTS) "
                    "VALUES (?, ?, ?, ?)",
                    file_id,
                    process_type_id,
                    complete_status_id,
                    updated_at,
                )
            else:
                cursor.execute(
                    "INSERT INTO FileProcessStatus (FileID, ProcessTypeID, StatusID) VALUES (?, ?, ?)",
                    file_id,
                    process_type_id,
                    pending_status_id,
                )
    print(f"FileProcessStatus created and backfilled for {len(file_ids)} file(s).")


def _status_id(cursor, name: str) -> int:
    cursor.execute("SELECT StatusID FROM FileStatuses WHERE StatusName = ?", name)
    return cursor.fetchone()[0]


def _migrate_add_files_is_active(cursor) -> None:
    print("Adding IsActive to Files (so files can be deactivated without deleting them)...")
    cursor.execute("ALTER TABLE Files ADD IsActive BIT NOT NULL DEFAULT 1")
    print("Files.IsActive added - existing rows default to active.")


def _migrate_create_user_roles(cursor) -> None:
    """Users used to hold exactly one Role (Users.RoleID). Replaces it with a
    many-to-many join table so a user can hold multiple roles (e.g. Admin +
    Polish Artist) at once, editable later without re-creating the user."""
    print("Creating UserRoles (a user can hold multiple roles at once)...")
    cursor.execute(
        """
        CREATE TABLE UserRoles (
            UserRoleID INT IDENTITY(1,1) PRIMARY KEY,
            UserID     INT NOT NULL FOREIGN KEY REFERENCES Users(UserID),
            RoleID     INT NOT NULL FOREIGN KEY REFERENCES Roles(RoleID),
            CONSTRAINT UQ_UserRoles UNIQUE (UserID, RoleID)
        )
        """
    )
    cursor.execute("CREATE INDEX IX_UserRoles_Role ON UserRoles(RoleID)")
    cursor.execute("INSERT INTO UserRoles (UserID, RoleID) SELECT UserID, RoleID FROM Users")

    cursor.execute(
        """
        DECLARE @constraintName NVARCHAR(200);
        SELECT @constraintName = fk.name
        FROM sys.foreign_keys fk
        JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        JOIN sys.columns c ON c.object_id = fkc.parent_object_id AND c.column_id = fkc.parent_column_id
        WHERE fk.parent_object_id = OBJECT_ID('Users') AND c.name = 'RoleID';
        IF @constraintName IS NOT NULL
            EXEC('ALTER TABLE Users DROP CONSTRAINT [' + @constraintName + ']');
        """
    )
    cursor.execute("ALTER TABLE Users DROP COLUMN RoleID")
    print("UserRoles created and backfilled - Users.RoleID retired.")


def _index_exists(cursor, table: str, index_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(?) AND name = ?", table, index_name
    )
    return cursor.fetchone() is not None


def _migrate_add_audit_trail_indexes(cursor) -> None:
    print("Adding AuditTrail indexes (Timestamp/FileID/PerformedByUserID) for the audit viewer...")
    if not _index_exists(cursor, "AuditTrail", "IX_AuditTrail_Timestamp"):
        cursor.execute("CREATE INDEX IX_AuditTrail_Timestamp ON AuditTrail(Timestamp)")
    if not _index_exists(cursor, "AuditTrail", "IX_AuditTrail_File"):
        cursor.execute("CREATE INDEX IX_AuditTrail_File ON AuditTrail(FileID)")
    if not _index_exists(cursor, "AuditTrail", "IX_AuditTrail_PerformedBy"):
        cursor.execute("CREATE INDEX IX_AuditTrail_PerformedBy ON AuditTrail(PerformedByUserID)")
    print("AuditTrail indexes added.")


def _migrate_add_taskassignments_date_indexes(cursor) -> None:
    print("Adding TaskAssignments date indexes (AssignedTS, CompletionTS+StatusID) for the calendar...")
    if not _index_exists(cursor, "TaskAssignments", "IX_TaskAssignments_AssignedTS"):
        cursor.execute("CREATE INDEX IX_TaskAssignments_AssignedTS ON TaskAssignments(AssignedTS)")
    if not _index_exists(cursor, "TaskAssignments", "IX_TaskAssignments_CompletionTS_Status"):
        cursor.execute(
            "CREATE INDEX IX_TaskAssignments_CompletionTS_Status ON TaskAssignments(CompletionTS, StatusID)"
        )
    print("TaskAssignments date indexes added.")


def _migrate_add_fileprocessstatus_completion_index(cursor) -> None:
    print("Adding FileProcessStatus completion index for Reports...")
    cursor.execute(
        "CREATE INDEX IX_FileProcessStatus_ProcessType_Status_Completion "
        "ON FileProcessStatus(ProcessTypeID, StatusID, CompletionTS)"
    )
    print("FileProcessStatus completion index added.")


def _run_migrations(cursor) -> None:
    """Ordered, idempotent post-install migrations - each checks its own
    precondition so re-running apply_schema() is always safe."""
    if not _column_exists(cursor, "Categories", "PhaseID"):
        _migrate_categories_to_phase_scoped(cursor)
    if not _column_exists(cursor, "Phases", "IsActive"):
        _migrate_add_is_active(cursor)
    _migrate_add_failed_status(cursor)
    _migrate_add_revoked_status(cursor)
    if not _table_exists(cursor, "ProcessTypes"):
        _migrate_create_process_types(cursor)
    if not _table_exists(cursor, "WorkerProcessPaths"):
        _migrate_create_worker_process_paths(cursor)
    if not _column_exists(cursor, "Files", "CurrentPath"):
        _migrate_add_files_current_path(cursor)
    if not _column_exists(cursor, "TaskAssignments", "ProcessTypeID"):
        _migrate_add_process_type_to_task_assignments(cursor)
    if not _table_exists(cursor, "FileProcessStatus"):
        _migrate_create_file_process_status(cursor)
    if not _column_exists(cursor, "Files", "IsActive"):
        _migrate_add_files_is_active(cursor)
    if not _table_exists(cursor, "UserRoles"):
        _migrate_create_user_roles(cursor)
    if not _index_exists(cursor, "AuditTrail", "IX_AuditTrail_Timestamp"):
        _migrate_add_audit_trail_indexes(cursor)
    if not _index_exists(cursor, "TaskAssignments", "IX_TaskAssignments_AssignedTS"):
        _migrate_add_taskassignments_date_indexes(cursor)
    if not _index_exists(cursor, "FileProcessStatus", "IX_FileProcessStatus_ProcessType_Status_Completion"):
        _migrate_add_fileprocessstatus_completion_index(cursor)


def apply_schema() -> None:
    sql_text = SCHEMA_FILE.read_text(encoding="utf-8")
    # pyodbc has no concept of GO - split into batches the way sqlcmd/SSMS would.
    batches = _split_batches(sql_text)

    conn = _raw_connect(settings.db_name)
    try:
        cursor = conn.cursor()
        # 001_schema.sql has no IF NOT EXISTS guards on its CREATE TABLE statements,
        # so re-running it against an already-set-up database fails on the first
        # duplicate object. Setup is meant to be re-run safely (e.g. setup.ps1 after
        # dependencies are already installed), so skip straight to migrations once
        # the base schema is present.
        if _schema_already_applied(cursor):
            print(f"Schema already applied to '{settings.db_name}' - checking for pending migrations.")
            _run_migrations(cursor)
            return
        for batch in batches:
            statement = batch.strip()
            if not statement:
                continue
            cursor.execute(statement)
        print(f"Schema applied to '{settings.db_name}'.")
    finally:
        conn.close()


if __name__ == "__main__":
    create_database_if_missing()
    apply_schema()
