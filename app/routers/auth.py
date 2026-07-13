from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

import secrets

from app.database import get_db
from app.models import User
from app.schemas import ChangePasswordRequest, MeOut
from app.security import DUMMY_PASSWORD_HASH, create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

MAX_FAILED_LOGIN_ATTEMPTS = 3


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Deliberately one generic message for "no such user", "wrong password",
    # and "deactivated" (whether an admin did that manually or 3 failed
    # attempts just did it below) - reusing the existing IsActive gate as-is
    # rather than a separate lockout flag/message means a locked-out account
    # looks identical to any other deactivated one, both to an attacker
    # probing usernames and in the code path itself.
    user = db.scalar(select(User).where(User.Username == form_data.username))

    # Always run a bcrypt verify, even for a username that doesn't exist -
    # against DUMMY_PASSWORD_HASH in that case - so a nonexistent-user
    # response takes the same time as a wrong-password one. Skipping this
    # for unknown usernames would let an attacker enumerate valid accounts
    # purely from response latency (bcrypt verification dominates request time).
    password_hash = user.PasswordHash if user is not None else DUMMY_PASSWORD_HASH
    password_ok = verify_password(form_data.password, password_hash)

    if user is None or not user.IsActive or not password_ok:
        if user is not None and user.IsActive and not password_ok:
            user.FailedLoginCount += 1
            if user.FailedLoginCount >= MAX_FAILED_LOGIN_ATTEMPTS:
                # Same effect as an admin clicking Deactivate on the Users page -
                # requires that same admin permission to reactivate.
                user.IsActive = False
            db.commit()
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    user.FailedLoginCount = 0
    db.commit()
    token = create_access_token(user.UserID, user.SecurityStamp)
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
    # Rotating the stamp invalidates every token issued before this change -
    # including, deliberately, the one used to make this very request. Issue
    # a fresh one below so this session keeps working; any OTHER
    # browser/device still holding the old token is now logged out for real.
    current_user.SecurityStamp = secrets.token_hex(32)
    db.commit()
    new_token = create_access_token(current_user.UserID, current_user.SecurityStamp)
    return {"status": "password_changed", "access_token": new_token, "token_type": "bearer"}
