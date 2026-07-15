"""Self-service surface for any logged-in user (worker or admin) to manage
their own availability and leave - separate from app/routers/auth.py (which
stays focused on login/session, deliberately untouched here) and from
app/routers/users.py (the admin-driven equivalent for managing OTHER users,
plus admin's own row through that same admin path)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserLeave
from app.schemas import AvailabilityRequest, CreateLeaveRequest, MyProfileOut, UserLeaveOut
from app.security import get_current_user

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _to_leave_out(row: UserLeave) -> UserLeaveOut:
    return UserLeaveOut(id=row.UserLeaveID, userId=row.UserID, startDate=row.StartDate, endDate=row.EndDate, createdAt=row.CreatedAt)


@router.get("/me", response_model=MyProfileOut)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return MyProfileOut(
        userId=current_user.UserID,
        username=current_user.Username,
        roleNames=[r.RoleName for r in current_user.roles],
        phaseId=current_user.PhaseID,
        isAvailable=current_user.IsAvailable,
    )


@router.patch("/availability", response_model=MyProfileOut)
def update_my_availability(
    payload: AvailabilityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.IsAvailable = payload.is_available
    db.commit()
    db.refresh(current_user)
    return get_my_profile(current_user)


@router.get("/leave", response_model=list[UserLeaveOut])
def get_my_leave(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(UserLeave).where(UserLeave.UserID == current_user.UserID).order_by(UserLeave.StartDate.desc())
    ).all()
    return [_to_leave_out(r) for r in rows]


@router.post("/leave", response_model=UserLeaveOut, status_code=201)
def add_my_leave(
    payload: CreateLeaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = UserLeave(
        UserID=current_user.UserID,
        StartDate=payload.start_date,
        EndDate=payload.end_date,
        CreatedByUserID=current_user.UserID,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_leave_out(row)


@router.delete("/leave/{leave_id}")
def cancel_my_leave(
    leave_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(UserLeave, leave_id)
    if row is None or row.UserID != current_user.UserID:
        raise HTTPException(status_code=404, detail="Leave record not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted"}
