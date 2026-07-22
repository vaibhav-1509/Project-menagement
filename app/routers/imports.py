from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routers.workboard import get_or_create_settings
from app.schemas import CsvImportCommitRequest, CsvImportPreview
from app.security import require_admin
from app.services.csv_import import commit_import, parse_csv, parse_csv_simple, preview_import

router = APIRouter(prefix="/api/admin/imports", tags=["imports"])


@router.post("/preview", response_model=CsvImportPreview)
async def preview(
    file: UploadFile | None = None,
    file_names_text: str | None = Form(None),
    phase_name: str | None = Form(None),
    category_name: str | None = Form(None),
    sub_category_name: str | None = Form(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Three ways to supply rows, picked by what's present:
    - Full CSV (file given, phase_name omitted): every row carries its own
      file_name, phase_name, category_name, sub_category_name, source_path.
    - Manual CSV (file + phase_name given): the CSV is filename-only - Phase/
      Category/Sub-Category were picked once in the UI.
    - Manual typed entry (file_names_text given, no file): same as manual CSV
      but the names were typed directly in the UI instead of uploaded.
    All modes resolve source paths against the global All Pending folder path."""
    try:
        settings = get_or_create_settings(db)
        source_root_path = (settings.AllPendingPath or "").strip()
        if not source_root_path:
            raise ValueError("All Pending folder path is not set in Admin Settings. Please configure it in User Control.")

        if file is not None:
            raw = await file.read()
            if phase_name:
                rows = parse_csv_simple(
                    raw,
                    phase_name=phase_name,
                    category_name=category_name or None,
                    sub_category_name=sub_category_name or None,
                    source_root=source_root_path,
                )
            else:
                rows = parse_csv(raw, source_root=source_root_path)
        elif file_names_text is not None:
            if not phase_name:
                raise ValueError("Phase is required")
            rows = parse_csv_simple(
                file_names_text.encode("utf-8"),
                phase_name=phase_name,
                category_name=category_name or None,
                sub_category_name=sub_category_name or None,
                source_root=source_root_path,
            )
        else:
            raise ValueError("Either a CSV file or a list of file names is required")
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
