import secrets
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
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
