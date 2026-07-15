"""CSV import: duplicate detection + versioned commit.

Two-phase flow, mirroring the Admin UI:
  1. preview_import()  - pure read; tells the caller which rows are new and
                          which collide with an existing (FileName, PhaseID).
  2. commit_import()   - applies the admin's per-conflict choice
                          (skip / overwrite / new_version) inside one
                          transaction per row so a bad row can't half-apply.
"""

import csv
import io
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, FileRecord, FileStatus, FileVersion, ImportBatch, Phase, SubCategory
from app.schemas import (
    CsvImportCommitRequest,
    CsvImportConflict,
    CsvImportPreview,
    CsvImportRow,
    DuplicateResolution,
)


def parse_csv(raw_bytes: bytes) -> list[CsvImportRow]:
    text = raw_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for r in reader:
        rows.append(
            CsvImportRow(
                file_name=r["file_name"].strip(),
                phase_name=r["phase_name"].strip(),
                category_name=(r.get("category_name") or "").strip() or None,
                sub_category_name=(r.get("sub_category_name") or "").strip() or None,
                source_path=r["source_path"].strip(),
            )
        )
    return rows


def parse_csv_simple(
    raw_bytes: bytes,
    phase_name: str,
    category_name: str | None,
    sub_category_name: str | None,
    source_root: str,
) -> list[CsvImportRow]:
    """Manual-import mode: the CSV is just a list of file names (one per line,
    header optional) - Phase/Category/Sub-Category/source root are picked once
    in the UI instead of repeated on every row. Builds the same CsvImportRow
    shape as parse_csv() so preview_import/commit_import need no changes."""
    text = raw_bytes.decode("utf-8-sig")
    rows = []
    for line in csv.reader(io.StringIO(text)):
        if not line:
            continue
        file_name = line[0].strip()
        if not file_name or file_name.lower() == "file_name":
            continue
        rows.append(
            CsvImportRow(
                file_name=file_name,
                phase_name=phase_name,
                category_name=category_name,
                sub_category_name=sub_category_name,
                source_path=os.path.join(source_root, file_name),
            )
        )
    return rows


def preview_import(db: Session, rows: list[CsvImportRow]) -> CsvImportPreview:
    """Duplicate detection is by FileName alone, database-wide - a file already
    sitting in a different Phase/Category/Sub-Category is still the same file
    and must be flagged, not silently re-created under a second identity.

    Two distinct conflict sources, both surfaced the same way to the caller:
    - "database": the name already exists somewhere in FileRecords (any phase).
    - "batch": the name isn't in the database yet, but an earlier row in this
      same import already claims it - the first occurrence wins, everything
      after it is a conflict against that first occurrence."""
    new_rows: list[CsvImportRow] = []
    conflicts: list[CsvImportConflict] = []
    staged: dict[str, CsvImportRow] = {}  # file_name -> the row that will create it, for this batch only

    for row in rows:
        phase = db.scalar(select(Phase).where(Phase.PhaseName == row.phase_name))
        if phase is None:
            raise ValueError(f"Unknown phase '{row.phase_name}' for file '{row.file_name}'")

        existing = db.scalar(select(FileRecord).where(FileRecord.FileName == row.file_name))
        if existing is not None:
            existing_phase = db.get(Phase, existing.PhaseID)
            existing_category = db.get(Category, existing.CategoryID) if existing.CategoryID else None
            existing_sub_category = db.get(SubCategory, existing.SubCategoryID) if existing.SubCategoryID else None
            current_version = db.get(FileVersion, existing.CurrentVersionID) if existing.CurrentVersionID else None
            conflicts.append(
                CsvImportConflict(
                    row=row,
                    existing_file_id=existing.FileID,
                    existing_version_number=current_version.VersionNumber if current_version else 0,
                    existing_phase_name=existing_phase.PhaseName if existing_phase else None,
                    existing_category_name=existing_category.CategoryName if existing_category else None,
                    existing_sub_category_name=existing_sub_category.SubCategoryName if existing_sub_category else None,
                    conflict_scope="database",
                )
            )
            continue

        staged_row = staged.get(row.file_name)
        if staged_row is not None:
            conflicts.append(
                CsvImportConflict(
                    row=row,
                    existing_file_id=None,
                    existing_version_number=0,
                    existing_phase_name=staged_row.phase_name,
                    existing_category_name=staged_row.category_name,
                    existing_sub_category_name=staged_row.sub_category_name,
                    conflict_scope="batch",
                )
            )
            continue

        new_rows.append(row)
        staged[row.file_name] = row

    return CsvImportPreview(new_rows=new_rows, conflicts=conflicts)


def _lookup_or_create_category(db: Session, phase_id: int, name: str | None) -> int | None:
    """Categories are scoped per phase - the same name in two different phases
    is two different rows, so the lookup (and any implicit create) is always
    scoped by phase_id too."""
    if not name:
        return None
    category = db.scalar(
        select(Category).where(Category.PhaseID == phase_id, Category.CategoryName == name)
    )
    if category is None:
        category = Category(PhaseID=phase_id, CategoryName=name)
        db.add(category)
        db.flush()
    return category.CategoryID


def _lookup_or_create_subcategory(db: Session, category_id: int | None, name: str | None) -> int | None:
    if not name or category_id is None:
        return None
    sub = db.scalar(
        select(SubCategory).where(SubCategory.CategoryID == category_id, SubCategory.SubCategoryName == name)
    )
    if sub is None:
        sub = SubCategory(CategoryID=category_id, SubCategoryName=name)
        db.add(sub)
        db.flush()
    return sub.SubCategoryID


def commit_import(db: Session, request: CsvImportCommitRequest, imported_by_user_id: int, csv_filename: str) -> dict:
    """Applies every row in its own savepoint so one bad row doesn't abort the whole batch."""

    pending_status = db.scalar(select(FileStatus).where(FileStatus.StatusName == "Pending"))
    resolution_by_key = {
        (r.file_name, r.phase_name): r.resolution for r in request.resolutions
    }

    batch = ImportBatch(ImportedByUserID=imported_by_user_id, SourceCsvName=csv_filename)
    db.add(batch)
    db.flush()  # need ImportBatchID for FileVersions rows below

    created, updated, skipped, errors = 0, 0, 0, []

    for row in request.rows:
        try:
            with db.begin_nested():  # per-row savepoint
                phase = db.scalar(select(Phase).where(Phase.PhaseName == row.phase_name))
                if phase is None:
                    raise ValueError(f"Unknown phase '{row.phase_name}'")

                category_id = _lookup_or_create_category(db, phase.PhaseID, row.category_name)
                sub_category_id = _lookup_or_create_subcategory(db, category_id, row.sub_category_name)

                # Database-wide by name alone (matches preview_import) - a file
                # already sitting under a different Phase/Category is still the
                # same file and must never get re-created under a new identity.
                existing = db.scalar(select(FileRecord).where(FileRecord.FileName == row.file_name))

                if existing is None:
                    version = FileVersion(
                        FileID=None,  # set after flush below
                        VersionNumber=1,
                        SourcePath=row.source_path,
                        ImportBatchID=batch.ImportBatchID,
                    )
                    file_record = FileRecord(
                        FileName=row.file_name,
                        PhaseID=phase.PhaseID,
                        CategoryID=category_id,
                        SubCategoryID=sub_category_id,
                        StatusID=pending_status.StatusID,
                    )
                    db.add(file_record)
                    db.flush()  # get FileID
                    version.FileID = file_record.FileID
                    db.add(version)
                    db.flush()
                    file_record.CurrentVersionID = version.VersionID
                    created += 1
                    continue

                resolution = resolution_by_key.get((row.file_name, row.phase_name))
                if resolution is None or resolution == DuplicateResolution.SKIP:
                    skipped += 1
                    continue

                if resolution == DuplicateResolution.OVERWRITE:
                    current_version = db.get(FileVersion, existing.CurrentVersionID)
                    current_version.SourcePath = row.source_path
                    current_version.ImportBatchID = batch.ImportBatchID
                    updated += 1
                    continue

                if resolution == DuplicateResolution.NEW_VERSION:
                    max_version = db.scalar(
                        select(FileVersion.VersionNumber)
                        .where(FileVersion.FileID == existing.FileID)
                        .order_by(FileVersion.VersionNumber.desc())
                    ) or 0
                    new_version = FileVersion(
                        FileID=existing.FileID,
                        VersionNumber=max_version + 1,
                        SourcePath=row.source_path,
                        ImportBatchID=batch.ImportBatchID,
                    )
                    db.add(new_version)
                    db.flush()
                    existing.CurrentVersionID = new_version.VersionID
                    updated += 1

        except Exception as exc:  # noqa: BLE001 - row-level isolation, report and continue
            errors.append({"file_name": row.file_name, "phase_name": row.phase_name, "error": str(exc)})

    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}
