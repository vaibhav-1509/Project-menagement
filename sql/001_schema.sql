/* ============================================================================
   Project Management Tool - SQL Server schema
   Run against a dedicated database, e.g. CREATE DATABASE ProjectManagement;
   then switch context with USE ProjectManagement; before running this file.
   (Handled automatically by scripts/create_database.py - see that script.)
   ============================================================================ */

SET NOCOUNT ON;
GO

/* -------------------------------------------------------------------------
   Lookup tables
   ------------------------------------------------------------------------- */

CREATE TABLE Roles (
    RoleID      INT IDENTITY(1,1) PRIMARY KEY,
    RoleName    NVARCHAR(50) NOT NULL UNIQUE
);
GO

CREATE TABLE Phases (
    PhaseID     INT IDENTITY(1,1) PRIMARY KEY,
    PhaseName   NVARCHAR(50) NOT NULL UNIQUE,
    IsActive    BIT NOT NULL DEFAULT 1
);
GO

CREATE TABLE FileStatuses (
    StatusID    INT IDENTITY(1,1) PRIMARY KEY,
    StatusName  NVARCHAR(50) NOT NULL UNIQUE
);
GO

-- The fixed, ordered production pipeline every file moves through (Polish -> GLB
-- -> Render by default) - separate from Phases, which stay a free-form classification
-- axis. Admin-manageable like Phases/Categories, not hardcoded, so a 4th stage can be
-- added later without a code change.
CREATE TABLE ProcessTypes (
    ProcessTypeID   INT IDENTITY(1,1) PRIMARY KEY,
    ProcessTypeName NVARCHAR(50) NOT NULL UNIQUE,
    SortOrder       INT NOT NULL UNIQUE,
    IsActive        BIT NOT NULL DEFAULT 1
);
GO

CREATE TABLE Categories (
    CategoryID      INT IDENTITY(1,1) PRIMARY KEY,
    PhaseID         INT NOT NULL FOREIGN KEY REFERENCES Phases(PhaseID),
    CategoryName    NVARCHAR(100) NOT NULL,
    IsActive        BIT NOT NULL DEFAULT 1,
    CONSTRAINT UQ_Category_Name_Phase UNIQUE (PhaseID, CategoryName)
);
GO

CREATE TABLE SubCategories (
    SubCategoryID   INT IDENTITY(1,1) PRIMARY KEY,
    CategoryID      INT NOT NULL FOREIGN KEY REFERENCES Categories(CategoryID),
    SubCategoryName NVARCHAR(100) NOT NULL,
    IsActive        BIT NOT NULL DEFAULT 1,
    CONSTRAINT UQ_SubCategory UNIQUE (CategoryID, SubCategoryName)
);
GO

/* -------------------------------------------------------------------------
   Users & path configuration
   ------------------------------------------------------------------------- */

CREATE TABLE Users (
    UserID          INT IDENTITY(1,1) PRIMARY KEY,
    Username        NVARCHAR(100) NOT NULL UNIQUE,
    PasswordHash    NVARCHAR(255) NOT NULL,
    PhaseID         INT NULL FOREIGN KEY REFERENCES Phases(PhaseID),  -- NULL for Admin
    IsActive        BIT NOT NULL DEFAULT 1,
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- Many-to-many: a user can hold multiple roles at once (e.g. Admin + Polish
-- Artist). Only the 'Admin' role is functionally special anywhere in the app;
-- the rest are informational tags independent of WorkerProcessPaths eligibility.
CREATE TABLE UserRoles (
    UserRoleID      INT IDENTITY(1,1) PRIMARY KEY,
    UserID          INT NOT NULL FOREIGN KEY REFERENCES Users(UserID),
    RoleID          INT NOT NULL FOREIGN KEY REFERENCES Roles(RoleID),
    CONSTRAINT UQ_UserRoles UNIQUE (UserID, RoleID)
);
GO
CREATE INDEX IX_UserRoles_Role ON UserRoles(RoleID);
GO

CREATE TABLE PhasePaths (
    PhasePathID     INT IDENTITY(1,1) PRIMARY KEY,
    PhaseID         INT NOT NULL UNIQUE FOREIGN KEY REFERENCES Phases(PhaseID),
    RootPath        NVARCHAR(500) NOT NULL   -- e.g. \\server\share\Polish_Folder\
);
GO

-- Per (worker, process type): a worker may be enabled for several process types,
-- each with its own Pending/Complete folder pair - picked by the admin via the
-- folder browser, not assembled from a naming convention.
CREATE TABLE WorkerProcessPaths (
    WorkerProcessPathID INT IDENTITY(1,1) PRIMARY KEY,
    UserID          INT NOT NULL FOREIGN KEY REFERENCES Users(UserID),
    ProcessTypeID   INT NOT NULL FOREIGN KEY REFERENCES ProcessTypes(ProcessTypeID),
    PendingPath     NVARCHAR(500) NOT NULL,
    CompletePath    NVARCHAR(500) NOT NULL,
    IsActive        BIT NOT NULL DEFAULT 1,
    CONSTRAINT UQ_WorkerProcessPaths UNIQUE (UserID, ProcessTypeID)
);
GO

/* -------------------------------------------------------------------------
   Files, versions, imports
   ------------------------------------------------------------------------- */

CREATE TABLE ImportBatches (
    ImportBatchID   INT IDENTITY(1,1) PRIMARY KEY,
    ImportedByUserID INT NOT NULL FOREIGN KEY REFERENCES Users(UserID),
    ImportedAt      DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    SourceCsvName   NVARCHAR(255) NOT NULL
);
GO

CREATE TABLE Files (
    FileID              INT IDENTITY(1,1) PRIMARY KEY,
    FileName            NVARCHAR(255) NOT NULL,
    PhaseID             INT NOT NULL FOREIGN KEY REFERENCES Phases(PhaseID),
    CategoryID          INT NULL FOREIGN KEY REFERENCES Categories(CategoryID),
    SubCategoryID       INT NULL FOREIGN KEY REFERENCES SubCategories(SubCategoryID),
    StatusID            INT NOT NULL FOREIGN KEY REFERENCES FileStatuses(StatusID),
    AssignedToUserID    INT NULL FOREIGN KEY REFERENCES Users(UserID),
    CurrentVersionID    INT NULL,  -- FK added after FileVersions exists (circular ref)
    CurrentPath         NVARCHAR(500) NULL,  -- where the file's folder physically sits right now
    IsActive            BIT NOT NULL DEFAULT 1,
    CreatedAt           DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    UpdatedAt           DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_File_Name_Phase UNIQUE (FileName, PhaseID)
);
GO

CREATE TABLE FileVersions (
    VersionID       INT IDENTITY(1,1) PRIMARY KEY,
    FileID          INT NOT NULL FOREIGN KEY REFERENCES Files(FileID),
    VersionNumber   INT NOT NULL,
    SourcePath      NVARCHAR(500) NOT NULL,
    ImportBatchID   INT NOT NULL FOREIGN KEY REFERENCES ImportBatches(ImportBatchID),
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_File_Version UNIQUE (FileID, VersionNumber)
);
GO

ALTER TABLE Files
    ADD CONSTRAINT FK_Files_CurrentVersion FOREIGN KEY (CurrentVersionID)
        REFERENCES FileVersions(VersionID);
GO

/* -------------------------------------------------------------------------
   Assignments, audit trail, transfer log
   ------------------------------------------------------------------------- */

CREATE TABLE TaskAssignments (
    AssignmentID    INT IDENTITY(1,1) PRIMARY KEY,
    FileID          INT NOT NULL FOREIGN KEY REFERENCES Files(FileID),
    VersionID       INT NOT NULL FOREIGN KEY REFERENCES FileVersions(VersionID),
    ProcessTypeID   INT NOT NULL FOREIGN KEY REFERENCES ProcessTypes(ProcessTypeID),
    AssignedToUserID INT NOT NULL FOREIGN KEY REFERENCES Users(UserID),
    PhaseID         INT NOT NULL FOREIGN KEY REFERENCES Phases(PhaseID),
    StatusID        INT NOT NULL FOREIGN KEY REFERENCES FileStatuses(StatusID),
    AssignedTS      DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CompletionTS    DATETIME2 NULL,
    FailureReason   NVARCHAR(1000) NULL,   -- mandatory at the app layer when Outcome = Failed
    SourcePath      NVARCHAR(500) NULL,    -- this attempt's copy source (convenience copy)
    DestPath        NVARCHAR(500) NULL,    -- this attempt's copy destination (convenience copy)
    IsActive        BIT NOT NULL DEFAULT 1   -- exactly one active attempt per (file, process type)
);
GO

-- Enforce "one active attempt per (file, process type)" at the DB level - this is the
-- full attempt-history log: many IsActive=0 rows (past attempts) plus at most one
-- IsActive=1 row per (FileID, ProcessTypeID).
CREATE UNIQUE INDEX UQ_TaskAssignments_ActivePerFileProcessType
    ON TaskAssignments(FileID, ProcessTypeID)
    WHERE IsActive = 1;
GO

-- Supports the Calendar's per-day activity counts and the Reports completions queries.
CREATE INDEX IX_TaskAssignments_AssignedTS ON TaskAssignments(AssignedTS);
CREATE INDEX IX_TaskAssignments_CompletionTS_Status ON TaskAssignments(CompletionTS, StatusID);
GO

-- Current state per (file, process type) - denormalized so the dashboard grid never
-- needs to join TaskAssignments per row just to show "what's Polish/GLB/Render status
-- right now." TaskAssignments (above) remains the full history; this is the summary.
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
);
GO

CREATE TABLE AuditTrail (
    AuditTrailID        INT IDENTITY(1,1) PRIMARY KEY,
    FileID              INT NOT NULL FOREIGN KEY REFERENCES Files(FileID),
    AssignmentID        INT NULL FOREIGN KEY REFERENCES TaskAssignments(AssignmentID),
    Action              NVARCHAR(50) NOT NULL,   -- e.g. Reset, EditCompletionTime
    PerformedByUserID   INT NOT NULL FOREIGN KEY REFERENCES Users(UserID),
    OldValue            NVARCHAR(MAX) NULL,
    NewValue            NVARCHAR(MAX) NULL,
    Timestamp           DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO
CREATE INDEX IX_AuditTrail_Timestamp ON AuditTrail(Timestamp);
CREATE INDEX IX_AuditTrail_File ON AuditTrail(FileID);
CREATE INDEX IX_AuditTrail_PerformedBy ON AuditTrail(PerformedByUserID);
GO

CREATE TABLE FileTransferLog (
    TransferID      INT IDENTITY(1,1) PRIMARY KEY,
    FileID          INT NOT NULL FOREIGN KEY REFERENCES Files(FileID),
    AssignmentID    INT NULL FOREIGN KEY REFERENCES TaskAssignments(AssignmentID),
    SourcePath      NVARCHAR(500) NOT NULL,
    DestPath        NVARCHAR(500) NOT NULL,
    Step            NVARCHAR(20) NOT NULL,   -- Copy | Verify | Delete
    Status          NVARCHAR(20) NOT NULL,   -- Started | Success | Failed
    ErrorMessage    NVARCHAR(500) NULL,
    Timestamp       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

/* -------------------------------------------------------------------------
   Indexes for the query patterns the dashboard actually uses
   ------------------------------------------------------------------------- */

CREATE INDEX IX_Files_AssignedTo ON Files(AssignedToUserID);
CREATE INDEX IX_Files_Phase_Status ON Files(PhaseID, StatusID);
CREATE INDEX IX_TaskAssignments_File ON TaskAssignments(FileID);
CREATE INDEX IX_TaskAssignments_AssignedTo_Active ON TaskAssignments(AssignedToUserID, IsActive);
CREATE INDEX IX_FileTransferLog_File ON FileTransferLog(FileID);
CREATE INDEX IX_WorkerProcessPaths_ProcessType ON WorkerProcessPaths(ProcessTypeID, IsActive);
CREATE INDEX IX_FileProcessStatus_ProcessType_Status ON FileProcessStatus(ProcessTypeID, StatusID);
CREATE INDEX IX_FileProcessStatus_AssignedTo ON FileProcessStatus(AssignedToUserID);
-- Covers the Reports completions date-bucketing query and the taxonomy-progress
-- "completed file ids" subquery.
CREATE INDEX IX_FileProcessStatus_ProcessType_Status_Completion ON FileProcessStatus(ProcessTypeID, StatusID, CompletionTS);
GO

/* -------------------------------------------------------------------------
   Seed lookup data
   ------------------------------------------------------------------------- */

-- Phases are NOT seeded with Polish/GLB/Render - those are process types (below),
-- not phases. Phases are a free-form classification the admin defines from scratch
-- via the Categories page (see app/routers/taxonomy.py).
INSERT INTO Roles (RoleName) VALUES ('Admin'), ('Polish Artist'), ('GLB Artist'), ('Render Artist');
INSERT INTO FileStatuses (StatusName) VALUES ('Pending'), ('InProgress'), ('Transferring'), ('Complete'), ('Locked'), ('Error'), ('Failed'), ('Revoked');
INSERT INTO ProcessTypes (ProcessTypeName, SortOrder) VALUES ('Polish', 10), ('GLB', 20), ('Render', 30);
GO

/* -------------------------------------------------------------------------
   First-time Admin bootstrap
   Refuses to run again once an Admin already exists, so it can't be used
   to silently mint extra admin accounts after go-live.
   ------------------------------------------------------------------------- */

CREATE OR ALTER PROCEDURE sp_CreateFirstAdmin
    @Username       NVARCHAR(100),
    @PasswordHash   NVARCHAR(255)
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1 FROM Users u
        JOIN UserRoles ur ON ur.UserID = u.UserID
        JOIN Roles r ON r.RoleID = ur.RoleID
        WHERE r.RoleName = 'Admin'
    )
    BEGIN
        RAISERROR('An Admin account already exists. sp_CreateFirstAdmin only bootstraps the very first admin.', 16, 1);
        RETURN;
    END

    DECLARE @AdminRoleID INT = (SELECT RoleID FROM Roles WHERE RoleName = 'Admin');

    INSERT INTO Users (Username, PasswordHash, PhaseID, IsActive)
    VALUES (@Username, @PasswordHash, NULL, 1);

    DECLARE @NewUserID INT = SCOPE_IDENTITY();
    INSERT INTO UserRoles (UserID, RoleID) VALUES (@NewUserID, @AdminRoleID);

    SELECT @NewUserID AS NewAdminUserID;
END
GO

/* Usage (PasswordHash must already be hashed application-side - see app/security.py):
   EXEC sp_CreateFirstAdmin @Username = N'admin', @PasswordHash = N'<bcrypt-hash>';
*/
