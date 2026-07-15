"""Admin-adjustable knobs that don't belong to any single entity - currently
just the Workboard's low-workload/stale-assignment thresholds (see
app/routers/workboard.py). Backed by the AppSettings singleton row."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.workboard import get_or_create_settings
from app.schemas import AppSettingsOut, UpdateAppSettingsRequest
from app.security import require_admin

router = APIRouter(prefix="/api/admin/settings", tags=["settings"])


@router.get("", response_model=AppSettingsOut)
def get_settings(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    settings = get_or_create_settings(db)
    return AppSettingsOut(
        lowWorkloadThreshold=settings.LowWorkloadThreshold, staleAssignmentDays=settings.StaleAssignmentDays
    )


@router.put("", response_model=AppSettingsOut)
def update_settings(
    payload: UpdateAppSettingsRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    settings = get_or_create_settings(db)
    settings.LowWorkloadThreshold = payload.low_workload_threshold
    settings.StaleAssignmentDays = payload.stale_assignment_days
    db.commit()
    db.refresh(settings)
    return AppSettingsOut(
        lowWorkloadThreshold=settings.LowWorkloadThreshold, staleAssignmentDays=settings.StaleAssignmentDays
    )
