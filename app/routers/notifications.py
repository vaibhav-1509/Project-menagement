from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification, User
from app.schemas import NotificationOut, NotificationsPageOut
from app.security import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationsPageOut)
def list_notifications(
    limit: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = db.scalars(
        select(Notification)
        .where(Notification.RecipientUserID == current_user.UserID)
        .order_by(Notification.CreatedAt.desc())
        .limit(limit)
    ).all()
    unread_count = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.RecipientUserID == current_user.UserID, Notification.IsRead == False)  # noqa: E712
    )
    return NotificationsPageOut(
        items=[
            NotificationOut(
                id=n.NotificationID,
                type=n.NotificationType,
                message=n.Message,
                fileId=n.FileID,
                isRead=n.IsRead,
                createdAt=n.CreatedAt,
            )
            for n in items
        ],
        unreadCount=unread_count,
    )


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notif = db.get(Notification, notification_id)
    if notif is None or notif.RecipientUserID != current_user.UserID:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.IsRead = True
    db.commit()
    return {"status": "read"}


@router.post("/mark-all-read")
def mark_all_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(
        Notification.__table__.update()
        .where(Notification.RecipientUserID == current_user.UserID, Notification.IsRead == False)  # noqa: E712
        .values(IsRead=True)
    )
    db.commit()
    return {"status": "all_read"}
