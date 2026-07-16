import secrets
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

UserRoles = Table(
    "UserRoles",
    Base.metadata,
    Column("UserRoleID", Integer, primary_key=True, autoincrement=True),
    Column("UserID", ForeignKey("Users.UserID"), nullable=False),
    Column("RoleID", ForeignKey("Roles.RoleID"), nullable=False),
    UniqueConstraint("UserID", "RoleID", name="UQ_UserRoles"),
)


class Role(Base):
    __tablename__ = "Roles"

    RoleID: Mapped[int] = mapped_column(Integer, primary_key=True)
    RoleName: Mapped[str] = mapped_column(String(50), unique=True)

    users: Mapped[list["User"]] = relationship(secondary=UserRoles, back_populates="roles")


class Phase(Base):
    __tablename__ = "Phases"

    PhaseID: Mapped[int] = mapped_column(Integer, primary_key=True)
    PhaseName: Mapped[str] = mapped_column(String(50), unique=True)
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True)


class FileStatus(Base):
    __tablename__ = "FileStatuses"

    StatusID: Mapped[int] = mapped_column(Integer, primary_key=True)
    StatusName: Mapped[str] = mapped_column(String(50), unique=True)


class ProcessType(Base):
    __tablename__ = "ProcessTypes"

    ProcessTypeID: Mapped[int] = mapped_column(Integer, primary_key=True)
    ProcessTypeName: Mapped[str] = mapped_column(String(50), unique=True)
    SortOrder: Mapped[int] = mapped_column(Integer, unique=True)
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True)


class Category(Base):
    __tablename__ = "Categories"
    __table_args__ = (UniqueConstraint("PhaseID", "CategoryName"),)

    CategoryID: Mapped[int] = mapped_column(Integer, primary_key=True)
    PhaseID: Mapped[int] = mapped_column(ForeignKey("Phases.PhaseID"))
    CategoryName: Mapped[str] = mapped_column(String(100))
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True)


class SubCategory(Base):
    __tablename__ = "SubCategories"
    __table_args__ = (UniqueConstraint("CategoryID", "SubCategoryName"),)

    SubCategoryID: Mapped[int] = mapped_column(Integer, primary_key=True)
    CategoryID: Mapped[int] = mapped_column(ForeignKey("Categories.CategoryID"))
    SubCategoryName: Mapped[str] = mapped_column(String(100))
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "Users"

    UserID: Mapped[int] = mapped_column(Integer, primary_key=True)
    Username: Mapped[str] = mapped_column(String(100), unique=True)
    PasswordHash: Mapped[str] = mapped_column(String(255))
    PhaseID: Mapped[int | None] = mapped_column(ForeignKey("Phases.PhaseID"), nullable=True)
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True)
    CreatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Bumped on every password change/reset and randomized fresh on every
    # INSERT - embedded in every JWT and re-checked on every request, so a
    # token becomes worthless the moment the password changes, the account is
    # recreated, or (via a full database wipe) the whole row is replaced -
    # even if the new row happens to reuse the same UserID.
    SecurityStamp: Mapped[str] = mapped_column(String(64), default=lambda: secrets.token_hex(32))
    # Counts consecutive wrong-password attempts; reset to 0 on a successful
    # login or whenever the account is (re)activated. Reaching
    # MAX_FAILED_LOGIN_ATTEMPTS (app/routers/auth.py) sets IsActive=False -
    # the exact same Deactivate an admin can click manually, rather than a
    # separate lockout flag - so reactivating (admin permission required)
    # already works via the existing Activate/Deactivate toggle.
    FailedLoginCount: Mapped[int] = mapped_column(Integer, default=0)
    # Lightweight "not taking new work right now" flag - distinct from
    # IsActive, which gates login/account access entirely. Toggled by the
    # worker themselves (self-service) or by an admin, without deactivating
    # the account. Only affects the Assign/Reject picker's default filtering
    # (frontend-only) - never blocks assignment at the API level.
    IsAvailable: Mapped[bool] = mapped_column(Boolean, default=True)

    roles: Mapped[list["Role"]] = relationship(secondary=UserRoles, back_populates="users")


class PhasePath(Base):
    __tablename__ = "PhasePaths"

    PhasePathID: Mapped[int] = mapped_column(Integer, primary_key=True)
    PhaseID: Mapped[int] = mapped_column(ForeignKey("Phases.PhaseID"), unique=True)
    RootPath: Mapped[str] = mapped_column(String(500))


class WorkerProcessPath(Base):
    __tablename__ = "WorkerProcessPaths"
    __table_args__ = (UniqueConstraint("UserID", "ProcessTypeID"),)

    WorkerProcessPathID: Mapped[int] = mapped_column(Integer, primary_key=True)
    UserID: Mapped[int] = mapped_column(ForeignKey("Users.UserID"))
    ProcessTypeID: Mapped[int] = mapped_column(ForeignKey("ProcessTypes.ProcessTypeID"))
    PendingPath: Mapped[str] = mapped_column(String(500))
    CompletePath: Mapped[str] = mapped_column(String(500))
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True)


class ImportBatch(Base):
    __tablename__ = "ImportBatches"

    ImportBatchID: Mapped[int] = mapped_column(Integer, primary_key=True)
    ImportedByUserID: Mapped[int] = mapped_column(ForeignKey("Users.UserID"))
    ImportedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    SourceCsvName: Mapped[str] = mapped_column(String(255))


class FileRecord(Base):
    __tablename__ = "Files"
    __table_args__ = (UniqueConstraint("FileName", "PhaseID"),)

    FileID: Mapped[int] = mapped_column(Integer, primary_key=True)
    FileName: Mapped[str] = mapped_column(String(255))
    PhaseID: Mapped[int] = mapped_column(ForeignKey("Phases.PhaseID"))
    CategoryID: Mapped[int | None] = mapped_column(ForeignKey("Categories.CategoryID"), nullable=True)
    SubCategoryID: Mapped[int | None] = mapped_column(ForeignKey("SubCategories.SubCategoryID"), nullable=True)
    StatusID: Mapped[int] = mapped_column(ForeignKey("FileStatuses.StatusID"))
    AssignedToUserID: Mapped[int | None] = mapped_column(ForeignKey("Users.UserID"), nullable=True)
    CurrentVersionID: Mapped[int | None] = mapped_column(ForeignKey("FileVersions.VersionID"), nullable=True)
    CurrentPath: Mapped[str | None] = mapped_column(String(500), nullable=True)
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True)
    CreatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    UpdatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Fixed 4-value app-level label (see schemas.FilePriority) - not a lookup
    # table like ProcessTypes/Phases, since it's a small cosmetic set that
    # never needs admin CRUD. Defaults to Normal on every newly created file
    # (including CSV/manual import); bumped afterward directly in the grid.
    Priority: Mapped[str] = mapped_column(String(20), default="Normal")


class FileVersion(Base):
    __tablename__ = "FileVersions"
    __table_args__ = (UniqueConstraint("FileID", "VersionNumber"),)

    VersionID: Mapped[int] = mapped_column(Integer, primary_key=True)
    FileID: Mapped[int] = mapped_column(ForeignKey("Files.FileID"))
    VersionNumber: Mapped[int] = mapped_column(Integer)
    SourcePath: Mapped[str] = mapped_column(String(500))
    ImportBatchID: Mapped[int] = mapped_column(ForeignKey("ImportBatches.ImportBatchID"))
    CreatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TaskAssignment(Base):
    __tablename__ = "TaskAssignments"

    AssignmentID: Mapped[int] = mapped_column(Integer, primary_key=True)
    FileID: Mapped[int] = mapped_column(ForeignKey("Files.FileID"))
    VersionID: Mapped[int] = mapped_column(ForeignKey("FileVersions.VersionID"))
    ProcessTypeID: Mapped[int] = mapped_column(ForeignKey("ProcessTypes.ProcessTypeID"))
    AssignedToUserID: Mapped[int] = mapped_column(ForeignKey("Users.UserID"))
    PhaseID: Mapped[int] = mapped_column(ForeignKey("Phases.PhaseID"))
    StatusID: Mapped[int] = mapped_column(ForeignKey("FileStatuses.StatusID"))
    AssignedTS: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    CompletionTS: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    FailureReason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    SourcePath: Mapped[str | None] = mapped_column(String(500), nullable=True)
    DestPath: Mapped[str | None] = mapped_column(String(500), nullable=True)
    IsActive: Mapped[bool] = mapped_column(Boolean, default=True)


class FileProcessStatus(Base):
    __tablename__ = "FileProcessStatus"
    __table_args__ = (UniqueConstraint("FileID", "ProcessTypeID"),)

    FileProcessStatusID: Mapped[int] = mapped_column(Integer, primary_key=True)
    FileID: Mapped[int] = mapped_column(ForeignKey("Files.FileID"))
    ProcessTypeID: Mapped[int] = mapped_column(ForeignKey("ProcessTypes.ProcessTypeID"))
    StatusID: Mapped[int] = mapped_column(ForeignKey("FileStatuses.StatusID"))
    AssignedToUserID: Mapped[int | None] = mapped_column(ForeignKey("Users.UserID"), nullable=True)
    ActiveAssignmentID: Mapped[int | None] = mapped_column(ForeignKey("TaskAssignments.AssignmentID"), nullable=True)
    LastFailureReason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    StartedTS: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    CompletionTS: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    UpdatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditTrail(Base):
    __tablename__ = "AuditTrail"

    AuditTrailID: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    FileID: Mapped[int] = mapped_column(ForeignKey("Files.FileID"))
    AssignmentID: Mapped[int | None] = mapped_column(ForeignKey("TaskAssignments.AssignmentID"), nullable=True)
    Action: Mapped[str] = mapped_column(String(50))
    PerformedByUserID: Mapped[int] = mapped_column(ForeignKey("Users.UserID"))
    OldValue: Mapped[str | None] = mapped_column(String, nullable=True)
    NewValue: Mapped[str | None] = mapped_column(String, nullable=True)
    Timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notification(Base):
    """Bell-icon feed - lightweight, dismissible events. Separate from
    AuditTrail (the full admin override record): a notification is "something
    happened that you should look at," not a permanent audit fact. See
    app/services/notifications.py for the two emit points."""

    __tablename__ = "Notifications"

    NotificationID: Mapped[int] = mapped_column(Integer, primary_key=True)
    RecipientUserID: Mapped[int] = mapped_column(ForeignKey("Users.UserID"))
    NotificationType: Mapped[str] = mapped_column(String(50))
    FileID: Mapped[int | None] = mapped_column(ForeignKey("Files.FileID"), nullable=True)
    Message: Mapped[str] = mapped_column(String(500))
    IsRead: Mapped[bool] = mapped_column(Boolean, default=False)
    CreatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FileTransferLog(Base):
    __tablename__ = "FileTransferLog"

    TransferID: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    FileID: Mapped[int] = mapped_column(ForeignKey("Files.FileID"))
    AssignmentID: Mapped[int | None] = mapped_column(ForeignKey("TaskAssignments.AssignmentID"), nullable=True)
    SourcePath: Mapped[str] = mapped_column(String(500))
    DestPath: Mapped[str] = mapped_column(String(500))
    Step: Mapped[str] = mapped_column(String(20))
    Status: Mapped[str] = mapped_column(String(20))
    ErrorMessage: Mapped[str | None] = mapped_column(String(500), nullable=True)
    Timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AppSettings(Base):
    """Singleton row (AppSettingsID is always 1) holding admin-adjustable
    knobs that don't belong to any single entity - e.g. the Workboard's
    low-workload/stale-assignment thresholds. Read via a plain SELECT with
    no WHERE clause (there is only ever one row), not by hardcoding the PK."""

    __tablename__ = "AppSettings"
    __table_args__ = (CheckConstraint("AppSettingsID = 1"),)

    AppSettingsID: Mapped[int] = mapped_column(Integer, primary_key=True)
    LowWorkloadThreshold: Mapped[int] = mapped_column(Integer, default=5)
    StaleAssignmentDays: Mapped[int] = mapped_column(Integer, default=3)
    # The admin's own folder pair, same shape as a worker's WorkerProcessPath
    # (one shared Pending + one shared Complete, not per-phase - admin plays
    # the same role in the pipeline as any other worker), plus one extra
    # folder for the raw, unregistered, loose-file intake pool that exists
    # before anything is imported into the system at all.
    AllPendingPath: Mapped[str | None] = mapped_column(String(500), nullable=True)
    AdminPendingPath: Mapped[str | None] = mapped_column(String(500), nullable=True)
    AdminCompletePath: Mapped[str | None] = mapped_column(String(500), nullable=True)


class UserLeave(Base):
    """Full-history leave record - one row per requested date range, never
    mutated in place (mirrors TaskAssignment's append-only convention) so
    past and future leave both stay visible instead of a single overwritable
    date pair on Users."""

    __tablename__ = "UserLeave"

    UserLeaveID: Mapped[int] = mapped_column(Integer, primary_key=True)
    UserID: Mapped[int] = mapped_column(ForeignKey("Users.UserID"))
    StartDate: Mapped[date] = mapped_column(Date)
    EndDate: Mapped[date] = mapped_column(Date)
    CreatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    CreatedByUserID: Mapped[int] = mapped_column(ForeignKey("Users.UserID"))
