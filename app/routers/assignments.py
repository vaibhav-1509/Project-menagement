import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditTrail, FileProcessStatus, FileRecord, FileStatus, ProcessType, TaskAssignment, User
from app.schemas import FileProcessHistoryOut, FileProcessStageOut, MarkFailedRequest, ProcessAttemptOut
from app.security import get_current_user, require_admin, user_is_admin
from app.services.file_transfer import (
    FileLockedError,
    TransferVerificationError,
    complete_process_assignment,
    mark_assignment_failed,
)

router = APIRouter(tags=["assignments"])


def _status_id(db: Session, name: str) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == name))


@router.post("/api/assignments/{assignment_id}/complete")
def complete_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Flips the (file, process type) to Complete AND physically moves the
    file's folder from the worker's Pending folder into their own Complete
    folder - the handoff point the next stage's assign will read from."""
    try:
        result = complete_process_assignment(db, assignment_id, current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TransferVerificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "complete", "dest_path": result.dest_path}


@router.post("/api/assignments/{assignment_id}/fail")
def fail_assignment(
    assignment_id: int,
    payload: MarkFailedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Worker (or admin) reports they could not finish this stage - requires a
    reason, which stays visible to whoever picks up the reassignment. No
    physical file move; the folder stays exactly where it is."""
    try:
        mark_assignment_failed(db, assignment_id, payload.reason, current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": "failed"}


@router.post("/api/admin/files/{file_id}/reset")
def reset_file(
    file_id: int,
    process_type_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivates the file's active assignment for one process type and
    archives it to AuditTrail instead of deleting it, then flips that stage
    back to Pending/unassigned. No physical file move - the folder stays
    where it is."""
    file_record = db.get(FileRecord, file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")

    assignment = db.scalar(
        select(TaskAssignment).where(
            TaskAssignment.FileID == file_id,
            TaskAssignment.ProcessTypeID == process_type_id,
            TaskAssignment.IsActive == True,  # noqa: E712
        )
    )

    old_value = None
    if assignment is not None:
        old_value = json.dumps(
            {
                "assignment_id": assignment.AssignmentID,
                "assigned_to_user_id": assignment.AssignedToUserID,
                "status_id": assignment.StatusID,
            }
        )
        assignment.IsActive = False

    pending_status_id = _status_id(db, "Pending")
    stage_status = db.scalar(
        select(FileProcessStatus).where(
            FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == process_type_id
        )
    )
    if stage_status is not None:
        stage_status.StatusID = pending_status_id
        stage_status.AssignedToUserID = None
        stage_status.ActiveAssignmentID = None

    db.add(
        AuditTrail(
            FileID=file_id,
            AssignmentID=assignment.AssignmentID if assignment else None,
            Action="Reset",
            PerformedByUserID=current_user.UserID,
            OldValue=old_value,
            NewValue=json.dumps({"status": "Pending", "assigned_to_user_id": None}),
        )
    )
    db.commit()
    return {"status": "reset"}


@router.get("/api/files/{file_id}/process-history", response_model=FileProcessHistoryOut)
def get_process_history(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_record = db.get(FileRecord, file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")

    is_admin = user_is_admin(current_user)
    if not is_admin:
        was_involved = db.scalar(
            select(TaskAssignment.AssignmentID).where(
                TaskAssignment.FileID == file_id, TaskAssignment.AssignedToUserID == current_user.UserID
            )
        )
        if was_involved is None:
            raise HTTPException(status_code=403, detail="You have never been assigned to this file")

    process_types = db.scalars(select(ProcessType).where(ProcessType.IsActive == True).order_by(ProcessType.SortOrder)).all()  # noqa: E712
    statuses = {s.StatusID: s.StatusName for s in db.scalars(select(FileStatus)).all()}
    stage_statuses = {
        fps.ProcessTypeID: fps
        for fps in db.scalars(select(FileProcessStatus).where(FileProcessStatus.FileID == file_id)).all()
    }

    rows = db.execute(
        select(TaskAssignment, User.Username)
        .join(User, User.UserID == TaskAssignment.AssignedToUserID)
        .where(TaskAssignment.FileID == file_id)
        .order_by(TaskAssignment.AssignedTS)
    ).all()
    attempts_by_process_type: dict[int, list[ProcessAttemptOut]] = {}
    for assignment, username in rows:
        attempts_by_process_type.setdefault(assignment.ProcessTypeID, []).append(
            ProcessAttemptOut(
                assignmentId=assignment.AssignmentID,
                processTypeId=assignment.ProcessTypeID,
                processTypeName="",
                assignedToUserId=assignment.AssignedToUserID,
                assignedToUsername=username,
                statusId=assignment.StatusID,
                statusName=statuses.get(assignment.StatusID, "?"),
                assignedTs=assignment.AssignedTS,
                completionTs=assignment.CompletionTS,
                failureReason=assignment.FailureReason,
                sourcePath=assignment.SourcePath,
                destPath=assignment.DestPath,
                isActive=assignment.IsActive,
            )
        )

    stages = []
    for pt in process_types:
        stage_status = stage_statuses.get(pt.ProcessTypeID)
        attempts = attempts_by_process_type.get(pt.ProcessTypeID, [])
        for attempt in attempts:
            attempt.processTypeName = pt.ProcessTypeName
        stages.append(
            FileProcessStageOut(
                processTypeId=pt.ProcessTypeID,
                processTypeName=pt.ProcessTypeName,
                sortOrder=pt.SortOrder,
                statusId=stage_status.StatusID if stage_status else _status_id(db, "Pending"),
                statusName=statuses.get(stage_status.StatusID, "Pending") if stage_status else "Pending",
                assignedToUserId=stage_status.AssignedToUserID if stage_status else None,
                lastFailureReason=stage_status.LastFailureReason if stage_status else None,
                attempts=attempts,
            )
        )

    return FileProcessHistoryOut(fileId=file_id, fileName=file_record.FileName, stages=stages)
