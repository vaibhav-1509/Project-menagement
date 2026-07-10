from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import CsvImportCommitRequest, CsvImportPreview
from app.security import require_admin
from app.services.csv_import import commit_import, parse_csv, parse_csv_simple, preview_import

router = APIRouter(prefix="/api/admin/imports", tags=["imports"])


@router.post("/preview", response_model=CsvImportPreview)
async def preview(
    file: UploadFile,
    phase_name: str | None = Form(None),
    category_name: str | None = Form(None),
    sub_category_name: str | None = Form(None),
    source_root_path: str | None = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Two CSV shapes, picked by whether phase_name is supplied:
    - Full CSV (phase_name omitted): every row carries its own file_name,
      phase_name, category_name, sub_category_name, source_path.
    - Manual import (phase_name given): the CSV is filename-only - Phase/
      Category/Sub-Category/source root were picked once in the UI."""
    raw = await file.read()
    try:
        if phase_name:
            if not source_root_path:
                raise ValueError("Source folder path is required for a manual import")
            rows = parse_csv_simple(
                raw,
                phase_name=phase_name,
                category_name=category_name or None,
                sub_category_name=sub_category_name or None,
                source_root=source_root_path,
            )
        else:
            rows = parse_csv(raw)
        return preview_import(db, rows)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/commit")
def commit(
    request: CsvImportCommitRequest,
    csv_filename: str = "import.csv",
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return commit_import(db, request, imported_by_user_id=current_user.UserID, csv_filename=csv_filename)
