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
    assert_no_later_stage_started,
    complete_process_assignment,
    mark_assignment_failed,
    reopen_process_assignment,
)

router = APIRouter(tags=["assignments"])


def _status_id(db: Session, name: str) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == name))


def _assert_no_later_stage_started(db: Session, file_id: int, process_type: ProcessType, action: str) -> None:
    try:
        assert_no_later_stage_started(db, file_id, process_type, action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Filesystem error: {exc}") from exc

    return {"status": "complete", "dest_path": result.dest_path, "warning": result.warning}


@router.post("/api/files/{file_id}/reopen")
def reopen_file(
    file_id: int,
    process_type_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Self-service undo for 'I marked this Complete by mistake' - only the
    worker who completed it (or an admin) can reopen it, and it stays
    assigned to that same worker rather than being unassigned like Reset."""
    try:
        result = reopen_process_assignment(db, file_id, process_type_id, current_user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except FileLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TransferVerificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Filesystem error: {exc}") from exc

    return {"status": "reopened", "dest_path": result.dest_path, "warning": result.warning}


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

    process_type = db.get(ProcessType, process_type_id)
    if process_type is None:
        raise HTTPException(status_code=400, detail="Unknown process type")

    pending_status_id = _status_id(db, "Pending")
    _assert_no_later_stage_started(db, file_id, process_type, "reset")

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

    stage_status = db.scalar(
        select(FileProcessStatus).where(
            FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == process_type_id
        )
    )
    if stage_status is not None:
        stage_status.StatusID = pending_status_id
        stage_status.AssignedToUserID = None
        stage_status.ActiveAssignmentID = None
        # Clear the prior attempt's timestamps/reason too - otherwise a stage
        # reset back to Pending keeps showing a stale CompletionTS/StartedTS
        # from the attempt that was just undone.
        stage_status.StartedTS = None
        stage_status.CompletionTS = None
        stage_status.LastFailureReason = None

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


@router.post("/api/admin/files/{file_id}/revoke")
def revoke_file(
    file_id: int,
    process_type_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin undoes their OWN assignment mistake (wrong file, wrong worker) -
    unlike Reset (a legitimate workflow undo that keeps the historical
    record intact), Revoke also marks the mistaken attempt as Revoked so it
    no longer counts toward that worker's Calendar/Reports history, as if it
    never happened. Use Reset when real work happened and is being walked
    back for a workflow reason; use Revoke when the assignment itself was a
    mistake."""
    file_record = db.get(FileRecord, file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")

    process_type = db.get(ProcessType, process_type_id)
    if process_type is None:
        raise HTTPException(status_code=400, detail="Unknown process type")

    pending_status_id = _status_id(db, "Pending")
    revoked_status_id = _status_id(db, "Revoked")
    _assert_no_later_stage_started(db, file_id, process_type, "revoke")

    assignment = db.scalar(
        select(TaskAssignment)
        .where(TaskAssignment.FileID == file_id, TaskAssignment.ProcessTypeID == process_type_id)
        .order_by(TaskAssignment.AssignedTS.desc())
    )
    if assignment is None:
        raise HTTPException(status_code=400, detail="No assignment to revoke for this stage")

    old_value = json.dumps(
        {
            "assignment_id": assignment.AssignmentID,
            "assigned_to_user_id": assignment.AssignedToUserID,
            "status_id": assignment.StatusID,
        }
    )
    assignment.IsActive = False
    assignment.StatusID = revoked_status_id

    stage_status = db.scalar(
        select(FileProcessStatus).where(
            FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == process_type_id
        )
    )
    if stage_status is not None:
        stage_status.StatusID = pending_status_id
        stage_status.AssignedToUserID = None
        stage_status.ActiveAssignmentID = None
        stage_status.StartedTS = None
        stage_status.CompletionTS = None
        stage_status.LastFailureReason = None

    db.add(
        AuditTrail(
            FileID=file_id,
            AssignmentID=assignment.AssignmentID,
            Action="Revoked",
            PerformedByUserID=current_user.UserID,
            OldValue=old_value,
            NewValue=json.dumps({"status": "Revoked", "assigned_to_user_id": None}),
        )
    )
    db.commit()
    return {"status": "revoked"}


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
