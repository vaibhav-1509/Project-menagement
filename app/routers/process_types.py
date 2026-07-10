from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FileProcessStatus, ProcessType, User, WorkerProcessPath
from app.schemas import (
    CreateProcessTypeRequest,
    LookupItem,
    ProcessTypeAdminOut,
    ReorderProcessTypesRequest,
    UpdateTaxonomyNodeRequest,
)
from app.security import require_admin

router = APIRouter(prefix="/api/admin/process-types", tags=["process-types"])


@router.get("", response_model=list[ProcessTypeAdminOut])
def list_process_types(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    process_types = db.scalars(select(ProcessType).order_by(ProcessType.SortOrder)).all()
    worker_counts = dict(
        db.execute(
            select(WorkerProcessPath.ProcessTypeID, func.count(func.distinct(WorkerProcessPath.UserID)))
            .where(WorkerProcessPath.IsActive == True)  # noqa: E712
            .group_by(WorkerProcessPath.ProcessTypeID)
        ).all()
    )
    return [
        ProcessTypeAdminOut(
            id=pt.ProcessTypeID,
            name=pt.ProcessTypeName,
            sortOrder=pt.SortOrder,
            isActive=pt.IsActive,
            workerCount=worker_counts.get(pt.ProcessTypeID, 0),
        )
        for pt in process_types
    ]


@router.post("", response_model=LookupItem, status_code=201)
def create_process_type(
    request: CreateProcessTypeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    max_sort_order = db.scalar(select(func.max(ProcessType.SortOrder))) or 0
    process_type = ProcessType(ProcessTypeName=request.name, SortOrder=max_sort_order + 10)
    db.add(process_type)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="A process type with that name already exists") from exc
    db.refresh(process_type)
    return LookupItem(id=process_type.ProcessTypeID, name=process_type.ProcessTypeName)


@router.patch("/{process_type_id}")
def update_process_type(
    process_type_id: int,
    request: UpdateTaxonomyNodeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    process_type = db.get(ProcessType, process_type_id)
    if process_type is None:
        raise HTTPException(status_code=404, detail="Process type not found")
    if request.name is not None:
        name = request.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be blank")
        process_type.ProcessTypeName = name
    if request.is_active is not None:
        process_type.IsActive = request.is_active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="A process type with that name already exists") from exc
    return {"id": process_type.ProcessTypeID, "name": process_type.ProcessTypeName, "isActive": process_type.IsActive}


@router.post("/reorder")
def reorder_process_types(
    request: ReorderProcessTypesRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    process_types = {pt.ProcessTypeID: pt for pt in db.scalars(select(ProcessType)).all()}
    if set(request.ordered_ids) != set(process_types.keys()):
        raise HTTPException(status_code=400, detail="ordered_ids must include every process type exactly once")

    # Two passes: push everything to a disjoint temporary range first, since the
    # target SortOrder values (existing 10/20/30...) already exist on other rows
    # and would collide with the UNIQUE constraint if written directly.
    for offset, process_type_id in enumerate(request.ordered_ids):
        process_types[process_type_id].SortOrder = -(offset + 1)
    db.flush()
    for offset, process_type_id in enumerate(request.ordered_ids):
        process_types[process_type_id].SortOrder = (offset + 1) * 10
    db.commit()
    return {"status": "reordered"}


@router.delete("/{process_type_id}")
def delete_process_type(
    process_type_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    process_type = db.get(ProcessType, process_type_id)
    if process_type is None:
        raise HTTPException(status_code=404, detail="Process type not found")

    blockers = []
    if db.scalar(
        select(FileProcessStatus.FileProcessStatusID).where(FileProcessStatus.ProcessTypeID == process_type_id)
    ) is not None:
        blockers.append("files")
    if db.scalar(
        select(WorkerProcessPath.WorkerProcessPathID).where(WorkerProcessPath.ProcessTypeID == process_type_id)
    ) is not None:
        blockers.append("worker folder configurations")
    if blockers:
        raise HTTPException(status_code=400, detail=f"Cannot delete - still referenced by: {', '.join(blockers)}")

    db.delete(process_type)
    db.commit()
    return {"status": "deleted"}
