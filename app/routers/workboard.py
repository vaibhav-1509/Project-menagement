"""Admin control center: everything currently needing an admin's attention in
one place - stages waiting on an Approve/Reject decision, and workers whose
Pending queue is running low so they need more work assigned. The low-workload
list is computed live on every request (not stored - see
app/services/notifications.py for why that's a deliberate choice, not an
oversight) so it's always accurate as of this exact moment.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FileProcessStatus, FileRecord, FileStatus, ProcessType, User, WorkerProcessPath
from app.schemas import AdminWorkboardOut, LowWorkloadWorkerOut, PendingApprovalOut
from app.security import require_admin

router = APIRouter(prefix="/api/admin/workboard", tags=["workboard"])

# "less than 5 files ... admin can assign new files" - a worker whose current
# Pending-stage backlog drops below this is flagged as running low.
LOW_WORKLOAD_THRESHOLD = 5


def _status_id(db: Session, name: str) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == name))


@router.get("", response_model=AdminWorkboardOut)
def get_workboard(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
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
        if count < LOW_WORKLOAD_THRESHOLD:
            low_workload.append(LowWorkloadWorkerOut(userId=worker.UserID, username=worker.Username, pendingCount=count))
    low_workload.sort(key=lambda w: w.pendingCount)

    return AdminWorkboardOut(
        pendingApprovals=pending_approvals,
        lowWorkloadWorkers=low_workload,
        lowWorkloadThreshold=LOW_WORKLOAD_THRESHOLD,
        checkedWorkerCount=len(active_workers),
    )
