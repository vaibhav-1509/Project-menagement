"""Copy-Verify-Delete pipeline for moving a file's folder between stages of the
Polish -> GLB -> Render pipeline (or any admin-defined ProcessTypes list).

Invariant: the source folder is removed in exactly one place inside
_copy_verify_delete, and only after the destination copy has been verified.
Every step is logged to FileTransferLog *before* it is attempted so a crash
mid-transfer leaves a durable "Transferring" trail a reconciliation job can
find on restart, instead of an ambiguous half-moved folder.

Callers that drive this pipeline:
- assign_file_process: admin assigns a (file, process type) to a worker -
  copies from the file's current location into that worker's Pending folder.
- complete_process_assignment: a worker finishes their stage - copies from
  their Pending folder into their own Complete folder, and lands the stage on
  "Submitted" (awaiting admin review), not "Complete" directly.
- approve_process_assignment / reject_process_assignment: the admin review
  gate. Approve flips Submitted -> Complete (no file move - it's already in
  the worker's Complete folder), which is what actually unlocks the next
  stage's assign_file_process call. Reject flips the submitted attempt to
  "Repair" (distinct from the worker-initiated "Failed" below) and
  immediately re-enters the SAME stage with a fresh assignment - same worker
  by default, or a different eligible one - reusing assign_file_process's own
  transfer/validation mechanics via the shared _assign_stage helper.
- mark_assignment_failed: a worker gives up mid-stage (never submitted).
  Copies their in-progress folder from Pending into their own Complete
  folder - the same real-world "put it in the tray" handoff as a normal
  Complete - so that whichever admin action reassigns it next (same worker or
  a different one, via a plain assign_file_process call once the stage's
  ActiveAssignmentID is cleared) always sources the folder from Complete,
  exactly like the reject flow above. No path in this module ever transfers
  folder-to-folder between two different workers' Pending directories -
  every handoff always passes through a Complete folder first.
"""

import os
import shutil
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.security import user_is_admin
from app.services.notifications import create_notification, notify_admins

from app.models import (
    FileProcessStatus,
    FileRecord,
    FileStatus,
    FileTransferLog,
    FileVersion,
    ProcessType,
    TaskAssignment,
    User,
    WorkerProcessPath,
)


class FileLockedError(Exception):
    pass


class TransferVerificationError(Exception):
    pass


class SourceNotFoundError(OSError):
    """The recorded source folder doesn't exist on disk - most often because
    someone already moved the file manually outside the app. Distinct from a
    generic OSError so callers can choose to proceed (recording the intended
    destination for tracking/reporting) instead of reverting the whole
    operation, while still surfacing a warning that a manual move is needed."""


@dataclass
class TransferResult:
    assignment_id: int
    dest_path: str
    warning: str | None = None


def _status_id(db: Session, name: str) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == name))


def assert_no_later_stage_started(db: Session, file_id: int, process_type: ProcessType, action: str) -> None:
    """Shared guard for Reset/Revoke/Reopen - undoing an earlier stage out from
    under a later stage that's already started would violate sequential
    gating (e.g. reopening Polish while GLB is already assigned or complete)."""
    pending_status_id = _status_id(db, "Pending")
    later_process_types = db.scalars(
        select(ProcessType).where(ProcessType.IsActive == True, ProcessType.SortOrder > process_type.SortOrder)  # noqa: E712
    ).all()
    if not later_process_types:
        return
    later_stage_statuses = db.scalars(
        select(FileProcessStatus).where(
            FileProcessStatus.FileID == file_id,
            FileProcessStatus.ProcessTypeID.in_([pt.ProcessTypeID for pt in later_process_types]),
        )
    ).all()
    started = next(
        (s for s in later_stage_statuses if s.StatusID != pending_status_id or s.AssignedToUserID is not None),
        None,
    )
    if started is not None:
        later_pt_name = next(pt.ProcessTypeName for pt in later_process_types if pt.ProcessTypeID == started.ProcessTypeID)
        raise ValueError(
            f"Cannot {action} {process_type.ProcessTypeName} - {later_pt_name} has already started. {action.capitalize()} {later_pt_name} first."
        )


def _dir_signature(path: str) -> tuple[int, int]:
    """(file_count, total_bytes) - cheap integrity check for large SMB trees."""
    file_count = 0
    total_bytes = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            file_count += 1
            total_bytes += os.path.getsize(os.path.join(root, f))
    return file_count, total_bytes


def _log(db: Session, file_id: int, assignment_id: int | None, source: str, dest: str, step: str, status: str, error: str | None = None):
    db.add(
        FileTransferLog(
            FileID=file_id,
            AssignmentID=assignment_id,
            SourcePath=source,
            DestPath=dest,
            Step=step,
            Status=status,
            ErrorMessage=error,
        )
    )
    db.commit()


def _copy_verify_delete(db: Session, file_id: int, assignment_id: int, source_path: str, dest_path: str) -> None:
    """Mechanical Copy-Verify-Delete only - raises on failure without touching
    any FileRecord/TaskAssignment/FileProcessStatus rows. Callers own reverting
    their own state on exception; this function only ever mutates the filesystem
    and FileTransferLog."""
    _log(db, file_id, assignment_id, source_path, dest_path, "Copy", "Started")

    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copytree(source_path, dest_path)
    except PermissionError as exc:
        _log(db, file_id, assignment_id, source_path, dest_path, "Copy", "Failed", "File Locked")
        raise FileLockedError(f"Source folder is locked: {source_path}") from exc
    except FileNotFoundError as exc:
        _log(db, file_id, assignment_id, source_path, dest_path, "Copy", "Failed", "Source not found")
        raise SourceNotFoundError(f"Source folder not found: {source_path}") from exc
    except OSError as exc:
        _log(db, file_id, assignment_id, source_path, dest_path, "Copy", "Failed", str(exc))
        raise

    _log(db, file_id, assignment_id, source_path, dest_path, "Copy", "Success")

    _log(db, file_id, assignment_id, source_path, dest_path, "Verify", "Started")
    if _dir_signature(source_path) != _dir_signature(dest_path):
        shutil.rmtree(dest_path, ignore_errors=True)  # only the partial *destination* copy
        _log(db, file_id, assignment_id, source_path, dest_path, "Verify", "Failed", "File count/size mismatch")
        raise TransferVerificationError("Copy verification failed - source left untouched")

    _log(db, file_id, assignment_id, source_path, dest_path, "Verify", "Success")

    try:
        shutil.rmtree(source_path)
        _log(db, file_id, assignment_id, source_path, dest_path, "Delete", "Success")
    except OSError as exc:
        # Destination is already verified - this is a cleanup failure, not data loss.
        _log(db, file_id, assignment_id, source_path, dest_path, "Delete", "Failed", str(exc))


def assign_file_process(db: Session, file_id: int, process_type_id: int, target_user_id: int) -> TransferResult:
    return _assign_stage(db, file_id, process_type_id, target_user_id)


def _assign_stage(
    db: Session, file_id: int, process_type_id: int, target_user_id: int, *, failure_reason: str | None = None
) -> TransferResult:
    """Shared by assign_file_process (a fresh stage) and reject_process_assignment's
    redo (re-entering the SAME stage after a Repair verdict). `failure_reason`
    is None for a plain assign (clears any stale reason, current behavior) or
    the rejection reason for a reject-triggered redo, so FilesGrid's existing
    ⚠ lastFailureReason tooltip shows the worker why their submission was
    rejected for the entire lifetime of the redo. No gate here needs to be
    skipped for the reject case: by the time this runs, reject_process_assignment
    has already committed the stage to Repair with ActiveAssignmentID cleared,
    so the "stage already has an active assignment"/"already Complete" checks
    below pass exactly as they would for any ordinary fresh assign."""
    file_record = db.get(FileRecord, file_id)
    if file_record is None:
        raise ValueError("File not found")

    process_type = db.get(ProcessType, process_type_id)
    if process_type is None or not process_type.IsActive:
        raise ValueError("Unknown or inactive process type")

    target_user = db.get(User, target_user_id)
    if target_user is None or not target_user.IsActive:
        raise ValueError("Target user not found or inactive")

    worker_path = db.scalar(
        select(WorkerProcessPath).where(
            WorkerProcessPath.UserID == target_user_id,
            WorkerProcessPath.ProcessTypeID == process_type_id,
            WorkerProcessPath.IsActive == True,  # noqa: E712
        )
    )
    if worker_path is None:
        raise ValueError(
            f"{target_user.Username} is not enabled for {process_type.ProcessTypeName}, "
            "or their Pending/Complete folders are not configured"
        )

    # Stage-order gating: the immediately preceding active process type must be
    # Complete for this file before this one can be assigned.
    previous_process_type = db.scalar(
        select(ProcessType)
        .where(ProcessType.IsActive == True, ProcessType.SortOrder < process_type.SortOrder)  # noqa: E712
        .order_by(ProcessType.SortOrder.desc())
    )
    complete_status_id = _status_id(db, "Complete")
    if previous_process_type is not None:
        previous_status = db.scalar(
            select(FileProcessStatus).where(
                FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == previous_process_type.ProcessTypeID
            )
        )
        if previous_status is None or previous_status.StatusID != complete_status_id:
            raise ValueError(f"{previous_process_type.ProcessTypeName} must be Complete before {process_type.ProcessTypeName} can be assigned")

    stage_status = db.scalar(
        select(FileProcessStatus).where(FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == process_type_id)
    )
    if stage_status is not None:
        if stage_status.ActiveAssignmentID is not None:
            raise ValueError(f"{process_type.ProcessTypeName} already has an active assignment for this file")
        if stage_status.StatusID == complete_status_id:
            raise ValueError(f"{process_type.ProcessTypeName} is already Complete for this file")

    source_path = file_record.CurrentPath
    if not source_path:
        version = db.get(FileVersion, file_record.CurrentVersionID)
        if version is None:
            raise ValueError("File has no known location (no CurrentPath and no version on record)")
        source_path = version.SourcePath

    dest_path = os.path.join(worker_path.PendingPath, file_record.FileName)

    transferring_id = _status_id(db, "Transferring")
    pending_id = _status_id(db, "Pending")

    # --- durability checkpoint, committed before any filesystem I/O ---
    previous_stage_status_id = stage_status.StatusID if stage_status else pending_id
    previous_assigned_to = stage_status.AssignedToUserID if stage_status else None
    previous_failure_reason = stage_status.LastFailureReason if stage_status else None

    assignment = TaskAssignment(
        FileID=file_id,
        VersionID=file_record.CurrentVersionID,
        ProcessTypeID=process_type_id,
        AssignedToUserID=target_user_id,
        PhaseID=file_record.PhaseID,
        StatusID=transferring_id,
        SourcePath=source_path,
        DestPath=dest_path,
        IsActive=True,
    )
    db.add(assignment)
    db.flush()

    if stage_status is None:
        stage_status = FileProcessStatus(FileID=file_id, ProcessTypeID=process_type_id, StatusID=transferring_id)
        db.add(stage_status)
    else:
        stage_status.StatusID = transferring_id
    stage_status.AssignedToUserID = target_user_id
    stage_status.ActiveAssignmentID = assignment.AssignmentID
    stage_status.StartedTS = datetime.utcnow()
    stage_status.LastFailureReason = failure_reason
    db.commit()
    db.refresh(assignment)

    # Reassigning a failed stage back to the same worker (folders never having
    # moved after a fail - see mark_assignment_failed) means source and
    # destination are literally the same folder. shutil.copytree can't copy a
    # directory into itself, and there's nothing to transfer anyway.
    warning = None
    if os.path.normpath(source_path) != os.path.normpath(dest_path):
        try:
            _copy_verify_delete(db, file_id, assignment.AssignmentID, source_path, dest_path)
        except SourceNotFoundError:
            # The file isn't where the system expects it - most likely someone
            # already moved it manually outside the app. Record the assignment
            # for tracking/reporting anyway (that's the whole point of the
            # portal for this workflow) rather than blocking on a filesystem
            # check, but flag that the physical file still needs a manual move.
            warning = (
                f"Source folder not found at {source_path} - assignment recorded, but the file "
                f"was not copied. Please move it into {dest_path} manually."
            )
        except (FileLockedError, TransferVerificationError, OSError):
            assignment.IsActive = False
            stage_status.StatusID = previous_stage_status_id
            stage_status.AssignedToUserID = previous_assigned_to
            stage_status.ActiveAssignmentID = None
            stage_status.LastFailureReason = previous_failure_reason
            db.commit()
            raise

    # --- commit the outcome ---
    file_record.CurrentPath = dest_path
    file_record.StatusID = pending_id
    file_record.AssignedToUserID = target_user_id
    assignment.StatusID = pending_id
    stage_status.StatusID = pending_id
    create_notification(
        db,
        target_user_id,
        "FileAssigned",
        f"You were assigned '{file_record.FileName}' for {process_type.ProcessTypeName}",
        file_id=file_id,
    )
    db.commit()

    return TransferResult(assignment_id=assignment.AssignmentID, dest_path=dest_path, warning=warning)


def complete_process_assignment(db: Session, assignment_id: int, current_user: User) -> TransferResult:
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None or not assignment.IsActive:
        raise ValueError("Active assignment not found")

    is_admin = user_is_admin(current_user)
    if not is_admin and assignment.AssignedToUserID != current_user.UserID:
        raise PermissionError("This assignment does not belong to you")

    worker_path = db.scalar(
        select(WorkerProcessPath).where(
            WorkerProcessPath.UserID == assignment.AssignedToUserID,
            WorkerProcessPath.ProcessTypeID == assignment.ProcessTypeID,
        )
    )
    if worker_path is None:
        raise ValueError("Worker's folder configuration for this process type is missing")

    file_record = db.get(FileRecord, assignment.FileID)
    source_path = file_record.CurrentPath
    if not source_path:
        raise ValueError("File has no known current location")
    dest_path = os.path.join(worker_path.CompletePath, file_record.FileName)

    stage_status = db.scalar(
        select(FileProcessStatus).where(
            FileProcessStatus.FileID == assignment.FileID, FileProcessStatus.ProcessTypeID == assignment.ProcessTypeID
        )
    )

    submitted_id = _status_id(db, "Submitted")

    warning = None
    try:
        _copy_verify_delete(db, assignment.FileID, assignment.AssignmentID, source_path, dest_path)
    except SourceNotFoundError:
        # Same rationale as assign_file_process - someone likely already moved
        # the file manually. Mark the stage Submitted for tracking/reporting
        # purposes, but flag that the physical file still needs a manual move.
        warning = (
            f"Source folder not found at {source_path} - marked Submitted, but the file was not "
            f"copied. Please move it into {dest_path} manually."
        )
    except (FileLockedError, TransferVerificationError, OSError):
        # Retryable - the assignment stays active/in-progress, nothing reverted.
        raise

    file_record.CurrentPath = dest_path
    file_record.StatusID = submitted_id
    assignment.StatusID = submitted_id
    assignment.IsActive = False
    if stage_status is not None:
        stage_status.StatusID = submitted_id
        # CompletionTS/ActiveAssignmentID are intentionally left as-is here:
        # CompletionTS stays None until an admin actually Approves (see
        # approve_process_assignment below) - that's the one moment Reports/
        # Calendar's "Completed" metrics should key off, not "worker clicked
        # Complete" - and ActiveAssignmentID keeps pointing at this assignment
        # so approve/reject can resolve "the thing awaiting my decision" with
        # no extra query, which also means assign_file_process's own
        # "stage already has an active assignment" gate already blocks anyone
        # from re-assigning a Submitted stage without any change to that check.
    process_type = db.get(ProcessType, assignment.ProcessTypeID)
    notify_admins(
        db,
        "SubmittedForApproval",
        f"{current_user.Username} submitted '{file_record.FileName}' ({process_type.ProcessTypeName}) for approval",
        file_id=assignment.FileID,
    )
    db.commit()

    return TransferResult(assignment_id=assignment.AssignmentID, dest_path=dest_path, warning=warning)


def approve_process_assignment(db: Session, file_id: int, process_type_id: int) -> int:
    """Admin approves a Submitted stage: flips it to Complete (CompletionTS set
    now, at approval time - not at the earlier submission time - since that's
    what Reports/Calendar's "Completed" metrics key off), unlocking the next
    stage's normal assign flow exactly as a plain Complete used to. No
    filesystem I/O - the file already sits in the worker's Complete folder
    from when they submitted it. Admin-only; enforced by the router's
    require_admin dependency, not here (same convention as assign_file_process/
    reset_file/revoke_file - no legitimate non-admin caller exists)."""
    process_type = db.get(ProcessType, process_type_id)
    if process_type is None:
        raise ValueError("Unknown process type")

    submitted_id = _status_id(db, "Submitted")
    stage_status = db.scalar(
        select(FileProcessStatus).where(
            FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == process_type_id
        )
    )
    if stage_status is None or stage_status.StatusID != submitted_id:
        raise ValueError(f"{process_type.ProcessTypeName} is not awaiting approval")

    assignment = db.get(TaskAssignment, stage_status.ActiveAssignmentID) if stage_status.ActiveAssignmentID else None
    if assignment is None:
        raise ValueError("No submitted assignment found to approve")

    complete_id = _status_id(db, "Complete")
    now = datetime.utcnow()
    assignment.StatusID = complete_id
    assignment.CompletionTS = now

    stage_status.StatusID = complete_id
    stage_status.CompletionTS = now
    stage_status.ActiveAssignmentID = None
    stage_status.LastFailureReason = None  # clear any stale Repair reason from an earlier reject cycle - resolved now

    file_record = db.get(FileRecord, file_id)
    file_record.StatusID = complete_id
    db.commit()
    return assignment.AssignmentID


def reject_process_assignment(
    db: Session, file_id: int, process_type_id: int, reason: str, reassign_to_user_id: int | None
) -> TransferResult:
    """Admin-initiated rejection of a Submitted stage for quality reasons -
    distinct from the worker-initiated mark_assignment_failed below (that one
    is "I can't finish this", untouched by this feature). Marks the submitted
    attempt Repair with the given reason (the permanent historical record,
    already visible for free in FileHistoryModal/process-history/report
    exports since those resolve status names/failure reasons generically),
    then immediately re-enters the SAME stage - not the next one - with a
    fresh assignment: to the same worker by default, or a different eligible
    one. Admin-only; enforced by the router's require_admin dependency."""
    file_record = db.get(FileRecord, file_id)
    if file_record is None:
        raise ValueError("File not found")

    process_type = db.get(ProcessType, process_type_id)
    if process_type is None:
        raise ValueError("Unknown process type")

    submitted_id = _status_id(db, "Submitted")
    stage_status = db.scalar(
        select(FileProcessStatus).where(
            FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == process_type_id
        )
    )
    if stage_status is None or stage_status.StatusID != submitted_id:
        raise ValueError(f"{process_type.ProcessTypeName} is not awaiting approval")

    old_assignment = db.get(TaskAssignment, stage_status.ActiveAssignmentID) if stage_status.ActiveAssignmentID else None
    if old_assignment is None:
        raise ValueError("No submitted assignment found to reject")

    repair_id = _status_id(db, "Repair")
    old_assignment.StatusID = repair_id
    old_assignment.FailureReason = reason
    old_assignment.CompletionTS = datetime.utcnow()
    # IsActive is already False since submission (complete_process_assignment
    # set it) - nothing here reactivates it.

    stage_status.StatusID = repair_id
    stage_status.LastFailureReason = reason
    stage_status.ActiveAssignmentID = None
    # Durability checkpoint: the Repair verdict survives even if the
    # reassignment below fails outright (e.g. a bad target user id) - same
    # "commit before the next step" rationale _assign_stage itself uses for
    # its own durability checkpoint before physical I/O.
    db.commit()

    target_user_id = reassign_to_user_id if reassign_to_user_id is not None else old_assignment.AssignedToUserID
    return _assign_stage(db, file_id, process_type_id, target_user_id, failure_reason=reason)


def reopen_process_assignment(db: Session, file_id: int, process_type_id: int, current_user: User) -> TransferResult:
    """Self-service undo for 'I marked this Complete by mistake' - unlike
    reset_file (an admin unassigning back to Pending/nobody), this keeps the
    SAME worker on the stage and moves the file back from their Complete
    folder into their Pending folder so they can keep working on it. Only the
    worker who completed it (or an admin) can reopen it."""
    file_record = db.get(FileRecord, file_id)
    if file_record is None:
        raise ValueError("File not found")

    process_type = db.get(ProcessType, process_type_id)
    if process_type is None:
        raise ValueError("Unknown process type")

    complete_id = _status_id(db, "Complete")
    stage_status = db.scalar(
        select(FileProcessStatus).where(
            FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == process_type_id
        )
    )
    if stage_status is None or stage_status.StatusID != complete_id:
        raise ValueError("This stage is not Complete - nothing to reopen")

    is_admin = user_is_admin(current_user)
    if not is_admin and stage_status.AssignedToUserID != current_user.UserID:
        raise PermissionError("This isn't your completed work to reopen")

    # Reopening this stage would undo its output while a later stage may
    # already be relying on it (assigned or further along) - same
    # pipeline-order guard Reset/Revoke use.
    assert_no_later_stage_started(db, file_id, process_type, "reopen")

    worker_id = stage_status.AssignedToUserID
    worker_path = db.scalar(
        select(WorkerProcessPath).where(
            WorkerProcessPath.UserID == worker_id, WorkerProcessPath.ProcessTypeID == process_type_id
        )
    )
    if worker_path is None:
        raise ValueError("Worker's folder configuration for this process type is missing")

    last_assignment = db.scalar(
        select(TaskAssignment)
        .where(
            TaskAssignment.FileID == file_id,
            TaskAssignment.ProcessTypeID == process_type_id,
            TaskAssignment.AssignedToUserID == worker_id,
        )
        .order_by(TaskAssignment.AssignedTS.desc())
    )
    if last_assignment is None:
        raise ValueError("No assignment record found to reopen")

    source_path = file_record.CurrentPath
    dest_path = os.path.join(worker_path.PendingPath, file_record.FileName)
    pending_id = _status_id(db, "Pending")

    warning = None
    if os.path.normpath(source_path) != os.path.normpath(dest_path):
        try:
            _copy_verify_delete(db, file_id, last_assignment.AssignmentID, source_path, dest_path)
        except SourceNotFoundError:
            warning = (
                f"Source folder not found at {source_path} - reopened for tracking, but the file "
                f"was not moved. Please move it into {dest_path} manually."
            )
        except (FileLockedError, TransferVerificationError, OSError):
            # Retryable - nothing reverted, stage stays Complete until this succeeds.
            raise

    last_assignment.IsActive = True
    last_assignment.StatusID = pending_id
    last_assignment.CompletionTS = None

    stage_status.StatusID = pending_id
    stage_status.ActiveAssignmentID = last_assignment.AssignmentID
    stage_status.CompletionTS = None

    file_record.CurrentPath = dest_path
    file_record.StatusID = pending_id
    db.commit()

    return TransferResult(assignment_id=last_assignment.AssignmentID, dest_path=dest_path, warning=warning)


def mark_assignment_failed(db: Session, assignment_id: int, reason: str, current_user: User) -> TransferResult:
    """Worker (or admin) reports they could not finish this stage. Same
    Pending -> Complete handoff as complete_process_assignment (the worker's
    real-world act of putting whatever they have into their Complete tray for
    the admin to deal with), just landing on Failed instead of Submitted -
    so reassignment (same worker or a different one, via the normal
    assign_file_process flow once ActiveAssignmentID is cleared below) always
    picks the folder up from the Complete folder, exactly like the reject
    flow already does for admin-rejected work. The reason is kept on both the
    historical TaskAssignments row and the FileProcessStatus summary so
    whoever picks up the reassignment can see what went wrong and who hit it."""
    assignment = db.get(TaskAssignment, assignment_id)
    if assignment is None or not assignment.IsActive:
        raise ValueError("Active assignment not found")

    is_admin = user_is_admin(current_user)
    if not is_admin and assignment.AssignedToUserID != current_user.UserID:
        raise PermissionError("This assignment does not belong to you")

    worker_path = db.scalar(
        select(WorkerProcessPath).where(
            WorkerProcessPath.UserID == assignment.AssignedToUserID,
            WorkerProcessPath.ProcessTypeID == assignment.ProcessTypeID,
        )
    )
    if worker_path is None:
        raise ValueError("Worker's folder configuration for this process type is missing")

    file_record = db.get(FileRecord, assignment.FileID)
    source_path = file_record.CurrentPath
    if not source_path:
        raise ValueError("File has no known current location")
    dest_path = os.path.join(worker_path.CompletePath, file_record.FileName)

    failed_id = _status_id(db, "Failed")

    warning = None
    if os.path.normpath(source_path) != os.path.normpath(dest_path):
        try:
            _copy_verify_delete(db, assignment.FileID, assignment.AssignmentID, source_path, dest_path)
        except SourceNotFoundError:
            # Same rationale as complete_process_assignment - someone likely
            # already moved the file manually. Mark Failed for tracking
            # purposes anyway, but flag that the physical file still needs a
            # manual move into the Complete folder.
            warning = (
                f"Source folder not found at {source_path} - marked Failed, but the file was not "
                f"copied. Please move it into {dest_path} manually."
            )
        except (FileLockedError, TransferVerificationError, OSError):
            # Retryable - the assignment stays active, nothing reverted.
            raise
    else:
        # Already sitting in this worker's Complete folder (e.g. failing again
        # after a prior fail/reject cycle put it there) - nothing to move.
        dest_path = source_path

    now = datetime.utcnow()
    assignment.StatusID = failed_id
    assignment.FailureReason = reason
    assignment.CompletionTS = now
    assignment.IsActive = False

    file_record.CurrentPath = dest_path

    stage_status = db.scalar(
        select(FileProcessStatus).where(
            FileProcessStatus.FileID == assignment.FileID, FileProcessStatus.ProcessTypeID == assignment.ProcessTypeID
        )
    )
    if stage_status is not None:
        stage_status.StatusID = failed_id
        stage_status.LastFailureReason = reason
        stage_status.ActiveAssignmentID = None
        # AssignedToUserID is kept (not cleared) so the failing worker stays
        # visible to whoever reassigns this stage next.
    db.commit()

    return TransferResult(assignment_id=assignment.AssignmentID, dest_path=dest_path, warning=warning)
