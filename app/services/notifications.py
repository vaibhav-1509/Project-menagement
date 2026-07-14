"""Bell-icon notifications - a lightweight, dismissible event feed, distinct
from AuditTrail (the permanent admin-facing record of every override:
Reset/Revoke/Approved/Rejected). A notification is "something happened that
you should look at," not a permanent audit fact - workers only ever see
their own, admins only ever see their own.

Two emit points today, both called from app/services/file_transfer.py:
- create_notification: a worker gets one when a stage becomes newly assigned
  to them - called from _assign_stage, which covers a direct admin Assign
  AND a reject's same/different-worker redo for free, since both go through
  that one shared helper.
- notify_admins: every active admin gets one when a worker submits a stage
  for review (complete_process_assignment).

"Low on work" reminders are deliberately NOT stored here - see
app/routers/workboard.py. That's a continuously-true/false condition (how
many files does this worker currently have queued), not a one-time event, so
it's computed live on each workboard/bell fetch instead of persisted as a
dismissible row that would need its own re-trigger/cooldown logic to avoid
either spamming a new row every poll or going stale once resolved.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification, Role, User, UserRoles


def create_notification(
    db: Session, recipient_user_id: int, notification_type: str, message: str, file_id: int | None = None
) -> None:
    """Adds to the session without committing - the caller's own commit (the
    same one that persists the state change this notification is about)
    covers it, so a notification only ever exists for a change that actually
    happened."""
    db.add(
        Notification(
            RecipientUserID=recipient_user_id,
            NotificationType=notification_type,
            FileID=file_id,
            Message=message,
        )
    )


def notify_admins(db: Session, notification_type: str, message: str, file_id: int | None = None) -> None:
    admin_ids = db.scalars(
        select(User.UserID)
        .join(UserRoles, UserRoles.c.UserID == User.UserID)
        .join(Role, Role.RoleID == UserRoles.c.RoleID)
        .where(Role.RoleName == "Admin", User.IsActive == True)  # noqa: E712
    ).all()
    for admin_id in admin_ids:
        create_notification(db, admin_id, notification_type, message, file_id)
