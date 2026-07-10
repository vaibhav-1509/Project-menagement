from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditTrail, FileRecord, User
from app.schemas import AuditTrailEntryOut, AuditTrailFilterParams, AuditTrailPageOut
from app.security import require_admin

router = APIRouter(prefix="/api/admin/audit-trail", tags=["audit-trail"])


@router.get("", response_model=AuditTrailPageOut)
def list_audit_trail(
    filters: AuditTrailFilterParams = Depends(),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = select(AuditTrail)
    if filters.file_id is not None:
        query = query.where(AuditTrail.FileID == filters.file_id)
    if filters.user_id is not None:
        query = query.where(AuditTrail.PerformedByUserID == filters.user_id)
    if filters.action is not None:
        query = query.where(AuditTrail.Action == filters.action)
    if filters.date_from is not None:
        query = query.where(AuditTrail.Timestamp >= filters.date_from)
    if filters.date_to is not None:
        query = query.where(AuditTrail.Timestamp <= filters.date_to)

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    rows = db.scalars(
        query.order_by(AuditTrail.Timestamp.desc())
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    ).all()

    file_ids = {r.FileID for r in rows}
    user_ids = {r.PerformedByUserID for r in rows}
    file_names = dict(db.execute(select(FileRecord.FileID, FileRecord.FileName).where(FileRecord.FileID.in_(file_ids))).all()) if file_ids else {}
    usernames = dict(db.execute(select(User.UserID, User.Username).where(User.UserID.in_(user_ids))).all()) if user_ids else {}

    items = [
        AuditTrailEntryOut(
            auditTrailId=r.AuditTrailID,
            fileId=r.FileID,
            fileName=file_names.get(r.FileID, f"#{r.FileID}"),
            action=r.Action,
            performedByUserId=r.PerformedByUserID,
            performedByUsername=usernames.get(r.PerformedByUserID, f"#{r.PerformedByUserID}"),
            oldValue=r.OldValue,
            newValue=r.NewValue,
            timestamp=r.Timestamp,
        )
        for r in rows
    ]
    return AuditTrailPageOut(items=items, total=total, page=filters.page, pageSize=filters.page_size)
