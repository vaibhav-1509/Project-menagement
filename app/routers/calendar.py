import calendar as calendar_module
from datetime import date as date_cls, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FileRecord, FileStatus, ProcessType, TaskAssignment, User
from app.schemas import CalendarDayCountOut, CalendarDayDetailOut, CalendarEventOut, CalendarMonthOut
from app.security import get_current_user, user_is_admin

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _status_id(db: Session, name: str) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == name))


def _scope_user_id(current_user: User, user_id: int | None) -> int | None:
    """Non-admins always see only their own activity, regardless of what
    user_id they pass - admins may optionally scope to one worker or leave it
    unset to see everyone (mirrors dashboard.list_files's scoping rule)."""
    if user_is_admin(current_user):
        return user_id
    return current_user.UserID


@router.get("/activity", response_model=CalendarMonthOut)
def get_activity(
    year: int,
    month: int,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    effective_user_id = _scope_user_id(current_user, user_id)
    days_in_month = calendar_module.monthrange(year, month)[1]
    first_day = date_cls(year, month, 1)
    next_month_start = first_day + timedelta(days=days_in_month)

    complete_id = _status_id(db, "Complete")
    failed_id = _status_id(db, "Failed")

    # Excludes assignment rows that were reset or reverted (e.g. the source
    # folder wasn't found and the copy was aborted) - those never actually took
    # effect, so counting them as "Assigned" activity would overstate today's
    # real work. A row only counts here if it's still active, or if it reached
    # a genuine terminal outcome (Complete/Failed).
    assigned_q = (
        select(cast(TaskAssignment.AssignedTS, Date), func.count())
        .where(
            TaskAssignment.AssignedTS >= first_day,
            TaskAssignment.AssignedTS < next_month_start,
            or_(TaskAssignment.IsActive == True, TaskAssignment.StatusID.in_([complete_id, failed_id])),  # noqa: E712
        )
        .group_by(cast(TaskAssignment.AssignedTS, Date))
    )
    completed_q = (
        select(cast(TaskAssignment.CompletionTS, Date), func.count())
        .where(
            TaskAssignment.CompletionTS >= first_day,
            TaskAssignment.CompletionTS < next_month_start,
            TaskAssignment.StatusID == complete_id,
        )
        .group_by(cast(TaskAssignment.CompletionTS, Date))
    )
    failed_q = (
        select(cast(TaskAssignment.CompletionTS, Date), func.count())
        .where(
            TaskAssignment.CompletionTS >= first_day,
            TaskAssignment.CompletionTS < next_month_start,
            TaskAssignment.StatusID == failed_id,
        )
        .group_by(cast(TaskAssignment.CompletionTS, Date))
    )

    if effective_user_id is not None:
        assigned_q = assigned_q.where(TaskAssignment.AssignedToUserID == effective_user_id)
        completed_q = completed_q.where(TaskAssignment.AssignedToUserID == effective_user_id)
        failed_q = failed_q.where(TaskAssignment.AssignedToUserID == effective_user_id)

    assigned_counts = dict(db.execute(assigned_q).all())
    completed_counts = dict(db.execute(completed_q).all())
    failed_counts = dict(db.execute(failed_q).all())

    days = []
    for day_num in range(1, days_in_month + 1):
        d = date_cls(year, month, day_num)
        days.append(
            CalendarDayCountOut(
                date=d.isoformat(),
                assignedCount=assigned_counts.get(d, 0),
                completedCount=completed_counts.get(d, 0),
                failedCount=failed_counts.get(d, 0),
            )
        )
    return CalendarMonthOut(year=year, month=month, days=days)


@router.get("/day", response_model=CalendarDayDetailOut)
def get_day(
    date: str,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    effective_user_id = _scope_user_id(current_user, user_id)
    try:
        target_date = date_cls.fromisoformat(date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD") from exc
    next_day = target_date + timedelta(days=1)

    complete_id = _status_id(db, "Complete")
    failed_id = _status_id(db, "Failed")

    base_query = (
        select(TaskAssignment, User.Username, FileRecord.FileName, ProcessType.ProcessTypeName)
        .join(User, User.UserID == TaskAssignment.AssignedToUserID)
        .join(FileRecord, FileRecord.FileID == TaskAssignment.FileID)
        .join(ProcessType, ProcessType.ProcessTypeID == TaskAssignment.ProcessTypeID)
    )
    if effective_user_id is not None:
        base_query = base_query.where(TaskAssignment.AssignedToUserID == effective_user_id)

    assigned_rows = db.execute(
        base_query.where(
            TaskAssignment.AssignedTS >= target_date,
            TaskAssignment.AssignedTS < next_day,
            or_(TaskAssignment.IsActive == True, TaskAssignment.StatusID.in_([complete_id, failed_id])),  # noqa: E712
        )
    ).all()
    completion_rows = db.execute(
        base_query.where(TaskAssignment.CompletionTS >= target_date, TaskAssignment.CompletionTS < next_day)
    ).all()

    events = []
    for assignment, username, file_name, process_type_name in assigned_rows:
        events.append(
            CalendarEventOut(
                fileId=assignment.FileID,
                fileName=file_name,
                processTypeId=assignment.ProcessTypeID,
                processTypeName=process_type_name,
                assignedToUserId=assignment.AssignedToUserID,
                assignedToUsername=username,
                event="Assigned",
                eventTs=assignment.AssignedTS,
                failureReason=None,
            )
        )
    for assignment, username, file_name, process_type_name in completion_rows:
        event_name = "Completed" if assignment.StatusID == complete_id else "Failed" if assignment.StatusID == failed_id else "Updated"
        events.append(
            CalendarEventOut(
                fileId=assignment.FileID,
                fileName=file_name,
                processTypeId=assignment.ProcessTypeID,
                processTypeName=process_type_name,
                assignedToUserId=assignment.AssignedToUserID,
                assignedToUsername=username,
                event=event_name,
                eventTs=assignment.CompletionTS,
                failureReason=assignment.FailureReason,
            )
        )

    events.sort(key=lambda e: e.eventTs)
    return CalendarDayDetailOut(date=date, events=events)
