from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AuditTrail,
    FileProcessStatus,
    FileRecord,
    FileTransferLog,
    FileVersion,
    Phase,
    ProcessType,
    SubCategory,
    TaskAssignment,
    User,
    WorkerProcessPath,
)
from app.schemas import AssignRequest, BulkAssignRequest, MoveCategoryRequest, MovePhaseRequest, SetActiveRequest
from app.security import require_admin
from app.services.file_transfer import FileLockedError, TransferVerificationError, assign_file_process

router = APIRouter(prefix="/api/admin/files", tags=["admin"])


@router.patch("/{file_id}")
def set_file_active(
    file_id: int,
    request: SetActiveRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivating hides nothing on disk and keeps all history - it just marks
    the file as no longer live work, same rationale as Phase/Category IsActive."""
    file_record = db.get(FileRecord, file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")
    file_record.IsActive = request.is_active
    db.commit()
    return {"id": file_record.FileID, "isActive": file_record.IsActive}


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Hard delete - only allowed once nothing is actively in flight for this
    file. Cascades its own history (versions, assignments, stage status,
    transfer log, audit trail) since none of that means anything once the
    file record itself is gone."""
    file_record = db.get(FileRecord, file_id)
    if file_record is None:
        raise HTTPException(status_code=404, detail="File not found")

    active = db.scalar(
        select(TaskAssignment.AssignmentID).where(TaskAssignment.FileID == file_id, TaskAssignment.IsActive == True)  # noqa: E712
    )
    if active is not None:
        raise HTTPException(status_code=400, detail="Cannot delete - file has an active assignment. Reset it first.")

    db.execute(delete(FileTransferLog).where(FileTransferLog.FileID == file_id))
    db.execute(delete(AuditTrail).where(AuditTrail.FileID == file_id))
    db.execute(delete(FileProcessStatus).where(FileProcessStatus.FileID == file_id))
    db.execute(delete(TaskAssignment).where(TaskAssignment.FileID == file_id))
    file_record.CurrentVersionID = None  # must clear before FileVersions can be dropped (FK)
    db.flush()
    db.execute(delete(FileVersion).where(FileVersion.FileID == file_id))
    db.delete(file_record)
    db.commit()
    return {"status": "deleted"}


@router.post("/{file_id}/assign")
def assign(
    file_id: int,
    request: AssignRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = assign_file_process(db, file_id, request.process_type_id, request.user_id)
    except FileLockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TransferVerificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"Filesystem error: {exc}") from exc

    return {"assignment_id": result.assignment_id, "dest_path": result.dest_path, "warning": result.warning}


@router.post("/bulk-assign")
def bulk_assign(
    request: BulkAssignRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Assign multiple files to the same worker for the same process type.
    Each file is validated individually - files with active assignments,
    already-complete stages, or missing worker paths are skipped with reasons."""
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="No file IDs provided")

    # Validate user and process type once
    target_user = db.get(User, request.user_id)
    if target_user is None or not target_user.IsActive:
        raise HTTPException(status_code=400, detail="Target user not found or inactive")

    process_type = db.get(ProcessType, request.process_type_id)
    if process_type is None or not process_type.IsActive:
        raise HTTPException(status_code=400, detail="Unknown or inactive process type")

    worker_path = db.scalar(
        select(WorkerProcessPath).where(
            WorkerProcessPath.UserID == request.user_id,
            WorkerProcessPath.ProcessTypeID == request.process_type_id,
            WorkerProcessPath.IsActive == True,  # noqa: E712
        )
    )
    if worker_path is None:
        raise HTTPException(
            status_code=400,
            detail=f"{target_user.Username} is not enabled for {process_type.ProcessTypeName}, or their Pending/Complete folders are not configured",
        )

    # Check for files with active assignments for this process type
    active_file_ids = {
        row[0]
        for row in db.execute(
            select(TaskAssignment.FileID).where(
                TaskAssignment.FileID.in_(request.file_ids),
                TaskAssignment.ProcessTypeID == request.process_type_id,
                TaskAssignment.IsActive == True,  # noqa: E712
            )
        ).all()
    }

    complete_status_id = _status_id(db, "Complete")
    updated, skipped = 0, []

    for file_id in request.file_ids:
        file_record = db.get(FileRecord, file_id)
        if file_record is None:
            skipped.append({"file_id": file_id, "reason": "File not found"})
            continue
        if file_id in active_file_ids:
            skipped.append({"file_id": file_id, "reason": "Has an active assignment for this stage - reset it first"})
            continue

        # Check if stage is already Complete
        stage_status = db.scalar(
            select(FileProcessStatus).where(
                FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == request.process_type_id
            )
        )
        if stage_status is not None and stage_status.StatusID == complete_status_id:
            skipped.append({"file_id": file_id, "reason": f"{process_type.ProcessTypeName} is already Complete for this file"})
            continue

        # Check stage-order gating (previous stage must be Complete)
        previous_process_type = db.scalar(
            select(ProcessType)
            .where(ProcessType.IsActive == True, ProcessType.SortOrder < process_type.SortOrder)  # noqa: E712
            .order_by(ProcessType.SortOrder.desc())
        )
        if previous_process_type is not None:
            previous_status = db.scalar(
                select(FileProcessStatus).where(
                    FileProcessStatus.FileID == file_id, FileProcessStatus.ProcessTypeID == previous_process_type.ProcessTypeID
                )
            )
            if previous_status is None or previous_status.StatusID != complete_status_id:
                skipped.append(
                    {"file_id": file_id, "reason": f"{previous_process_type.ProcessTypeName} must be Complete before {process_type.ProcessTypeName} can be assigned"}
                )
                continue

        # All validations passed - assign the file
        try:
            result = assign_file_process(db, file_id, request.process_type_id, request.user_id)
            updated += 1
        except (FileLockedError, TransferVerificationError, ValueError, OSError) as exc:
            skipped.append({"file_id": file_id, "reason": str(exc)})
            continue

    return {"updated": updated, "skipped": skipped}


@router.post("/move-category")
def move_category(
    request: MoveCategoryRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reclassifies selected files' Category/Sub-Category. Pure metadata - no
    physical folder implication, so always allowed regardless of assignment state."""
    category_id = request.category_id
    if request.sub_category_id is not None:
        sub_category = db.get(SubCategory, request.sub_category_id)
        if sub_category is None:
            raise HTTPException(status_code=400, detail="Unknown sub-category")
        if category_id is not None and sub_category.CategoryID != category_id:
            raise HTTPException(status_code=400, detail="Sub-category does not belong to the given category")
        category_id = sub_category.CategoryID

    files = db.scalars(select(FileRecord).where(FileRecord.FileID.in_(request.file_ids))).all()
    found_ids = {f.FileID for f in files}
    missing = [fid for fid in request.file_ids if fid not in found_ids]

    for f in files:
        f.CategoryID = category_id
        f.SubCategoryID = request.sub_category_id
    db.commit()

    return {"updated": len(files), "missing_file_ids": missing}


@router.post("/move-phase")
def move_phase(
    request: MovePhaseRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reclassifies selected files' Phase. Unlike Category/Sub-Category this has
    a physical implication (PhasePaths root differs per phase), so any file with
    an active assignment - meaning its folder already sits under the OLD phase's
    root in someone's Pending/InProgress tree - is skipped, not force-moved.
    Reset it first, then move it, then re-Assign to actually relocate the folder."""
    phase = db.get(Phase, request.phase_id)
    if phase is None:
        raise HTTPException(status_code=400, detail="Unknown phase")

    active_file_ids = {
        row[0]
        for row in db.execute(
            select(TaskAssignment.FileID).where(
                TaskAssignment.FileID.in_(request.file_ids), TaskAssignment.IsActive == True  # noqa: E712
            )
        ).all()
    }

    updated, skipped = 0, []
    for file_id in request.file_ids:
        file_record = db.get(FileRecord, file_id)
        if file_record is None:
            skipped.append({"file_id": file_id, "reason": "File not found"})
            continue
        if file_id in active_file_ids:
            skipped.append({"file_id": file_id, "reason": "Has an active assignment - reset it first"})
            continue
        try:
            with db.begin_nested():
                file_record.PhaseID = request.phase_id
        except IntegrityError:
            skipped.append(
                {
                    "file_id": file_id,
                    "reason": f"A file named '{file_record.FileName}' already exists in {phase.PhaseName}",
                }
            )
        else:
            updated += 1

    db.commit()
    return {"updated": updated, "skipped": skipped}
