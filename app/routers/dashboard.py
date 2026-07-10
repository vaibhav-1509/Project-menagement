from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Category,
    FileProcessStatus,
    FileRecord,
    FileStatus,
    Phase,
    ProcessType,
    SubCategory,
    TaskAssignment,
    User,
)
from app.schemas import DashboardFilterParams, FileOut, FileProcessStageSummary
from app.security import get_current_user, user_is_admin

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/files", response_model=list[FileOut])
def list_files(
    filters: DashboardFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Role-based dashboard filtering.

    Admins can see and filter across every file. Artists are hard-scoped
    server-side to their own phase, and further to files where a
    FileProcessStatus row shows them as assigned on some stage - `assigned_to_user_id`
    on the request is ignored for non-admins so a crafted query string can't
    widen the view past what the UI exposes.
    """
    query = select(FileRecord)
    is_admin = user_is_admin(current_user)

    if is_admin:
        if filters.assigned_to_user_id is not None:
            assigned_query = select(FileProcessStatus.FileID).where(
                FileProcessStatus.AssignedToUserID == filters.assigned_to_user_id
            )
            if filters.process_type_id is not None:
                assigned_query = assigned_query.where(FileProcessStatus.ProcessTypeID == filters.process_type_id)
            query = query.where(FileRecord.FileID.in_(assigned_query))
    else:
        query = query.where(
            FileRecord.PhaseID == current_user.PhaseID,
            FileRecord.FileID.in_(
                select(FileProcessStatus.FileID).where(FileProcessStatus.AssignedToUserID == current_user.UserID)
            ),
        )

    if filters.phase_id is not None:
        query = query.where(FileRecord.PhaseID == filters.phase_id)
    if filters.category_id is not None:
        query = query.where(FileRecord.CategoryID == filters.category_id)
    if filters.sub_category_id is not None:
        query = query.where(FileRecord.SubCategoryID == filters.sub_category_id)
    if filters.is_active is not None:
        query = query.where(FileRecord.IsActive == filters.is_active)
    if filters.status_id is not None:
        if filters.process_type_id is not None:
            query = query.where(
                FileRecord.FileID.in_(
                    select(FileProcessStatus.FileID).where(
                        FileProcessStatus.ProcessTypeID == filters.process_type_id,
                        FileProcessStatus.StatusID == filters.status_id,
                    )
                )
            )
        else:
            query = query.where(FileRecord.StatusID == filters.status_id)

    if filters.search:
        term = f"%{_escape_like(filters.search)}%"
        query = query.where(
            or_(
                FileRecord.FileName.like(term, escape="\\"),
                FileRecord.PhaseID.in_(select(Phase.PhaseID).where(Phase.PhaseName.like(term, escape="\\"))),
                FileRecord.CategoryID.in_(
                    select(Category.CategoryID).where(Category.CategoryName.like(term, escape="\\"))
                ),
                FileRecord.SubCategoryID.in_(
                    select(SubCategory.SubCategoryID).where(SubCategory.SubCategoryName.like(term, escape="\\"))
                ),
            )
        )

    files = db.scalars(query.order_by(FileRecord.UpdatedAt.desc())).all()
    file_ids = [f.FileID for f in files]

    process_types = db.scalars(select(ProcessType).where(ProcessType.IsActive == True).order_by(ProcessType.SortOrder)).all()  # noqa: E712
    status_names = {s.StatusID: s.StatusName for s in db.scalars(select(FileStatus)).all()}

    stage_rows = (
        db.execute(select(FileProcessStatus).where(FileProcessStatus.FileID.in_(file_ids))).scalars().all()
        if file_ids
        else []
    )
    stages_by_file: dict[int, dict[int, FileProcessStatus]] = {}
    for row in stage_rows:
        stages_by_file.setdefault(row.FileID, {})[row.ProcessTypeID] = row

    my_active_rows = (
        db.execute(
            select(TaskAssignment.FileID, TaskAssignment.AssignmentID).where(
                TaskAssignment.FileID.in_(file_ids),
                TaskAssignment.AssignedToUserID == current_user.UserID,
                TaskAssignment.IsActive == True,  # noqa: E712
            )
        ).all()
        if file_ids
        else []
    )
    my_active_by_file = dict(my_active_rows)

    pending_status_id = next((sid for sid, name in status_names.items() if name == "Pending"), None)

    result = []
    for f in files:
        file_stages = stages_by_file.get(f.FileID, {})
        process_stages = []
        for pt in process_types:
            stage = file_stages.get(pt.ProcessTypeID)
            process_stages.append(
                FileProcessStageSummary(
                    processTypeId=pt.ProcessTypeID,
                    processTypeName=pt.ProcessTypeName,
                    sortOrder=pt.SortOrder,
                    statusId=stage.StatusID if stage else pending_status_id,
                    statusName=status_names.get(stage.StatusID, "Pending") if stage else "Pending",
                    assignedToUserId=stage.AssignedToUserID if stage else None,
                    activeAssignmentId=stage.ActiveAssignmentID if stage else None,
                    lastFailureReason=stage.LastFailureReason if stage else None,
                )
            )
        result.append(
            FileOut(
                FileID=f.FileID,
                FileName=f.FileName,
                PhaseID=f.PhaseID,
                CategoryID=f.CategoryID,
                SubCategoryID=f.SubCategoryID,
                StatusID=f.StatusID,
                AssignedToUserID=f.AssignedToUserID,
                CurrentVersionID=f.CurrentVersionID,
                ActiveAssignmentID=my_active_by_file.get(f.FileID),
                UpdatedAt=f.UpdatedAt,
                IsActive=f.IsActive,
                processStages=process_stages,
                myActiveAssignmentId=my_active_by_file.get(f.FileID),
            )
        )
    return result
