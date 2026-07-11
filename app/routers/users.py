import os
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import AuditTrail, ImportBatch, ProcessType, Role, TaskAssignment, User, UserRoles, WorkerProcessPath
from app.schemas import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserOut,
    WorkerProcessPathIn,
    WorkerProcessPathOut,
)
from app.security import hash_password, require_admin, user_is_admin

router = APIRouter(prefix="/api/admin/users", tags=["users"])


def _to_user_out(db: Session, u: User) -> UserOut:
    enabled_ids = db.scalars(
        select(WorkerProcessPath.ProcessTypeID).where(
            WorkerProcessPath.UserID == u.UserID, WorkerProcessPath.IsActive == True  # noqa: E712
        )
    ).all()
    return UserOut(
        UserID=u.UserID,
        Username=u.Username,
        roleNames=[r.RoleName for r in u.roles],
        roleIds=[r.RoleID for r in u.roles],
        PhaseID=u.PhaseID,
        IsActive=u.IsActive,
        enabledProcessTypeIds=list(enabled_ids),
    )


def _resolve_roles(db: Session, role_ids: list[int]) -> list[Role]:
    roles = db.scalars(select(Role).where(Role.RoleID.in_(role_ids))).all()
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=400, detail="Unknown role in role_ids")
    return list(roles)


def _active_admin_count(db: Session, exclude_user_id: int | None = None) -> int:
    query = (
        select(func.count(func.distinct(User.UserID)))
        .select_from(User)
        .join(UserRoles, UserRoles.c.UserID == User.UserID)
        .join(Role, Role.RoleID == UserRoles.c.RoleID)
        .where(Role.RoleName == "Admin", User.IsActive == True)  # noqa: E712
    )
    if exclude_user_id is not None:
        query = query.where(User.UserID != exclude_user_id)
    return db.scalar(query)


@router.get("", response_model=list[UserOut])
def list_users(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only user directory - powers the Assign modal's user picker, the
    dashboard's 'Assigned To' filter/column, and the User Management page."""
    users = db.scalars(select(User).options(selectinload(User.roles))).all()
    return [_to_user_out(db, u) for u in users]


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: CreateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    roles = _resolve_roles(db, payload.role_ids)
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = User(
        Username=payload.username,
        PasswordHash=hash_password(payload.password),
        PhaseID=payload.phase_id,
        IsActive=True,
        roles=roles,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username already exists") from exc

    db.refresh(user)
    return _to_user_out(db, user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UpdateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    roles = _resolve_roles(db, payload.role_ids)

    was_active_admin = user_is_admin(user) and user.IsActive
    becomes_active_admin = any(r.RoleName == "Admin" for r in roles) and payload.is_active
    if was_active_admin and not becomes_active_admin and _active_admin_count(db, exclude_user_id=user_id) == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the last active Admin - promote another user to Admin first.",
        )

    user.roles = roles
    user.PhaseID = payload.phase_id
    user.IsActive = payload.is_active
    db.commit()
    db.refresh(user)
    return _to_user_out(db, user)


@router.post("/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    payload: ResetPasswordRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.PasswordHash = hash_password(payload.new_password)
    # Invalidates every token already issued to this user - an admin
    # resetting someone's password (e.g. suspected compromise) should kill
    # their existing sessions, not just block future logins with the old one.
    user.SecurityStamp = secrets.token_hex(32)
    db.commit()
    return {"status": "password_reset"}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Hard delete - blocked if the user has any assignment, import, or audit
    history, since deleting them would either orphan those records or erase
    who-did-what. Deactivate instead to remove someone from active work while
    keeping their history intact."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if (
        user_is_admin(user)
        and user.IsActive
        and _active_admin_count(db, exclude_user_id=user_id) == 0
    ):
        raise HTTPException(status_code=400, detail="Cannot delete the last active Admin - promote another user to Admin first.")

    blockers = []
    if db.scalar(select(TaskAssignment.AssignmentID).where(TaskAssignment.AssignedToUserID == user_id)) is not None:
        blockers.append("assignment history")
    if db.scalar(select(ImportBatch.ImportBatchID).where(ImportBatch.ImportedByUserID == user_id)) is not None:
        blockers.append("import history")
    if db.scalar(select(AuditTrail.AuditTrailID).where(AuditTrail.PerformedByUserID == user_id)) is not None:
        blockers.append("audit trail entries")
    if blockers:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete - still referenced by: {', '.join(blockers)}. Deactivate instead to preserve history.",
        )

    db.execute(delete(WorkerProcessPath).where(WorkerProcessPath.UserID == user_id))
    db.execute(delete(UserRoles).where(UserRoles.c.UserID == user_id))
    db.delete(user)
    db.commit()
    return {"status": "deleted"}


@router.get("/{user_id}/process-paths", response_model=list[WorkerProcessPathOut])
def get_process_paths(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    rows = db.execute(
        select(WorkerProcessPath, ProcessType.ProcessTypeName)
        .join(ProcessType, ProcessType.ProcessTypeID == WorkerProcessPath.ProcessTypeID)
        .where(WorkerProcessPath.UserID == user_id)
    ).all()
    return [
        WorkerProcessPathOut(
            processTypeId=wpp.ProcessTypeID,
            processTypeName=name,
            pendingPath=wpp.PendingPath,
            completePath=wpp.CompletePath,
            isActive=wpp.IsActive,
        )
        for wpp, name in rows
    ]


@router.put("/{user_id}/process-paths", response_model=list[WorkerProcessPathOut])
def set_process_paths(
    user_id: int,
    payload: list[WorkerProcessPathIn],
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full-replace: every process type the worker is enabled for must appear in
    the payload with both folders set. Anything previously configured but
    omitted from this payload is deactivated, never hard-deleted, so history
    (TaskAssignments referencing this worker's past paths) stays intact."""
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    seen_process_type_ids = set()
    for entry in payload:
        if entry.process_type_id in seen_process_type_ids:
            raise HTTPException(status_code=400, detail="Duplicate process_type_id in payload")
        seen_process_type_ids.add(entry.process_type_id)

        if db.get(ProcessType, entry.process_type_id) is None:
            raise HTTPException(status_code=400, detail=f"Unknown process type {entry.process_type_id}")
        if not os.path.isdir(entry.pending_path):
            raise HTTPException(status_code=400, detail=f"Pending path does not exist or is not accessible: {entry.pending_path}")
        if not os.path.isdir(entry.complete_path):
            raise HTTPException(status_code=400, detail=f"Complete path does not exist or is not accessible: {entry.complete_path}")
        if os.path.normpath(entry.pending_path) == os.path.normpath(entry.complete_path):
            raise HTTPException(status_code=400, detail="Pending and Complete paths must be different folders")

        existing = db.scalar(
            select(WorkerProcessPath).where(
                WorkerProcessPath.UserID == user_id, WorkerProcessPath.ProcessTypeID == entry.process_type_id
            )
        )
        if existing is None:
            db.add(
                WorkerProcessPath(
                    UserID=user_id,
                    ProcessTypeID=entry.process_type_id,
                    PendingPath=entry.pending_path,
                    CompletePath=entry.complete_path,
                    IsActive=entry.is_active,
                )
            )
        else:
            existing.PendingPath = entry.pending_path
            existing.CompletePath = entry.complete_path
            existing.IsActive = entry.is_active

    omitted = db.scalars(
        select(WorkerProcessPath).where(
            WorkerProcessPath.UserID == user_id, WorkerProcessPath.ProcessTypeID.not_in(seen_process_type_ids or [0])
        )
    ).all()
    for row in omitted:
        row.IsActive = False

    db.commit()
    return get_process_paths(user_id, current_user, db)
