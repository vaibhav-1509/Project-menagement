"""Admin control center: everything currently needing an admin's attention in
one place - stages waiting on an Approve/Reject decision, workers whose
Pending queue is running low so they need more work assigned, and assignments
that have sat un-submitted too long. The low-workload/stale lists are computed
live on every request (not stored - see app/services/notifications.py for why
that's a deliberate choice, not an oversight) so they're always accurate as of
this exact moment. Both thresholds are admin-adjustable (app/routers/settings.py)
instead of hardcoded.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppSettings, FileProcessStatus, FileRecord, FileStatus, ProcessType, TaskAssignment, User, WorkerProcessPath
from app.schemas import AdminWorkboardOut, LowWorkloadWorkerOut, PendingApprovalOut, StaleAssignmentOut
from app.security import require_admin

router = APIRouter(prefix="/api/admin/workboard", tags=["workboard"])


def _status_id(db: Session, name: str) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == name))


def get_or_create_settings(db: Session) -> AppSettings:
    """The AppSettings table always has exactly one seeded row (see the
    _migrate_create_app_settings migration) - this defensive create-if-missing
    is just insurance in case that row was somehow lost, matching this
    codebase's idempotent-migration ethos."""
    settings = db.scalars(select(AppSettings)).first()
    if settings is None:
        settings = AppSettings(AppSettingsID=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@router.get("", response_model=AdminWorkboardOut)
def get_workboard(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)
    submitted_id = _status_id(db, "Submitted")
    pending_id = _status_id(db, "Pending")

    pending_approvals = [
        PendingApprovalOut(
            fileId=stage_status.FileID,
            fileName=file_name,
            processTypeId=stage_status.ProcessTypeID,
            processTypeName=process_type_name,
            submittedByUserId=stage_status.AssignedToUserID,
            submittedByUsername=username,
            submittedAt=stage_status.UpdatedAt,
        )
        for stage_status, file_name, process_type_name, username in db.execute(
            select(FileProcessStatus, FileRecord.FileName, ProcessType.ProcessTypeName, User.Username)
            .join(FileRecord, FileRecord.FileID == FileProcessStatus.FileID)
            .join(ProcessType, ProcessType.ProcessTypeID == FileProcessStatus.ProcessTypeID)
            .join(User, User.UserID == FileProcessStatus.AssignedToUserID)
            .where(FileProcessStatus.StatusID == submitted_id)
            .order_by(FileProcessStatus.UpdatedAt)
        ).all()
    ]

    # Low workload: active users with at least one active WorkerProcessPath
    # (i.e. actually configured to receive work) whose current Pending-stage
    # backlog, across every process type they're enabled for, is below the
    # threshold. An admin account with no worker paths of its own never
    # shows up here - it was never meant to receive files.
    worker_ids = db.scalars(
        select(WorkerProcessPath.UserID).where(WorkerProcessPath.IsActive == True).distinct()  # noqa: E712
    ).all()

    pending_counts = {}
    if worker_ids:
        pending_counts = dict(
            db.execute(
                select(FileProcessStatus.AssignedToUserID, func.count())
                .where(
                    FileProcessStatus.StatusID == pending_id,
                    FileProcessStatus.AssignedToUserID.in_(worker_ids),
                )
                .group_by(FileProcessStatus.AssignedToUserID)
            ).all()
        )

    active_workers = []
    if worker_ids:
        active_workers = db.scalars(
            select(User).where(User.UserID.in_(worker_ids), User.IsActive == True)  # noqa: E712
        ).all()

    low_workload = []
    for worker in active_workers:
        count = pending_counts.get(worker.UserID, 0)
        if count < settings.LowWorkloadThreshold:
            low_workload.append(LowWorkloadWorkerOut(userId=worker.UserID, username=worker.Username, pendingCount=count))
    low_workload.sort(key=lambda w: w.pendingCount)

    # Stale: an assignment that's sat Pending (assigned, not yet submitted)
    # for longer than the configured window. A reject-triggered reassignment
    # creates a fresh TaskAssignment row (see reject_process_assignment), so
    # its AssignedTS correctly resets the clock for the new attempt.
    stale_cutoff = datetime.utcnow() - timedelta(days=settings.StaleAssignmentDays)
    stale_rows = db.execute(
        select(TaskAssignment, FileRecord.FileName, ProcessType.ProcessTypeName, User.Username)
        .join(FileRecord, FileRecord.FileID == TaskAssignment.FileID)
        .join(ProcessType, ProcessType.ProcessTypeID == TaskAssignment.ProcessTypeID)
        .join(User, User.UserID == TaskAssignment.AssignedToUserID)
        .where(
            TaskAssignment.IsActive == True,  # noqa: E712
            TaskAssignment.StatusID == pending_id,
            TaskAssignment.AssignedTS < stale_cutoff,
        )
        .order_by(TaskAssignment.AssignedTS)
    ).all()
    stale_assignments = [
        StaleAssignmentOut(
            assignmentId=assignment.AssignmentID,
            fileId=assignment.FileID,
            fileName=file_name,
            processTypeId=assignment.ProcessTypeID,
            processTypeName=process_type_name,
            assignedToUserId=assignment.AssignedToUserID,
            assignedToUsername=username,
            assignedTs=assignment.AssignedTS,
            ageDays=(datetime.utcnow() - assignment.AssignedTS).days,
        )
        for assignment, file_name, process_type_name, username in stale_rows
    ]

    return AdminWorkboardOut(
        pendingApprovals=pending_approvals,
        lowWorkloadWorkers=low_workload,
        lowWorkloadThreshold=settings.LowWorkloadThreshold,
        checkedWorkerCount=len(active_workers),
        staleAssignments=stale_assignments,
        staleAssignmentDays=settings.StaleAssignmentDays,
    )
