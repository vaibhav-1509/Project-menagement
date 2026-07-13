import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# A bcrypt hash of a value nobody will ever type, used as the comparison
# target when a username doesn't exist - see auth.py's login(). Verifying
# against this (instead of skipping verification entirely) costs the same
# bcrypt work as a real check, so response time doesn't leak whether the
# username exists.
DUMMY_PASSWORD_HASH = pwd_context.hash(secrets.token_hex(32))


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, security_stamp: str) -> str:
    # security_stamp is re-checked against the live User row on every request
    # (see get_current_user) - it's what makes a password change/reset, or a
    # full database wipe that happens to recreate the same UserID, actually
    # invalidate previously issued tokens instead of leaving them silently
    # valid until they naturally expire.
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": str(user_id), "sst": security_stamp, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def user_is_admin(user: User) -> bool:
    return any(r.RoleName == "Admin" for r in user.roles)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub"))
        token_stamp = payload.get("sst")
    except (JWTError, TypeError, ValueError):
        raise credentials_error

    user = db.get(User, user_id, options=[selectinload(User.roles)])
    if user is None or not user.IsActive:
        raise credentials_error
    # Reject tokens issued before the account's last password change/reset,
    # or against a since-deleted-and-recreated account that happens to reuse
    # the same UserID (e.g. after a full database wipe) - the stamp for that
    # is a fresh random value, so an old token's "sst" can never match it.
    if token_stamp != user.SecurityStamp:
        raise credentials_error
    return user


def require_roles(*allowed_role_names: str):
    """Dependency factory: raises 403 unless current_user holds at least one of allowed_role_names."""

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not any(r.RoleName in allowed_role_names for r in current_user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(allowed_role_names)}",
            )
        return current_user

    return dependency


require_admin = require_roles("Admin")
