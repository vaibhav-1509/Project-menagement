from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import ChangePasswordRequest, MeOut
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.Username == form_data.username))
    if user is None or not user.IsActive or not verify_password(form_data.password, user.PasswordHash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(user.UserID)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=MeOut)
def get_me(current_user: User = Depends(get_current_user)):
    """The JWT no longer embeds role names (they can change without requiring
    re-login), so the frontend fetches them fresh here once per token."""
    return MeOut(roleNames=[r.RoleName for r in current_user.roles])


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Self-service password change - any logged-in user (Admin or Artist), not
    just the admin panel. Requires the current password so a hijacked session
    token alone can't lock the real owner out."""
    if not verify_password(payload.current_password, current_user.PasswordHash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    current_user.PasswordHash = hash_password(payload.new_password)
    db.commit()
    return {"status": "password_changed"}
