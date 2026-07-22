from datetime import date as date_cls, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import Date, cast, false, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Category,
    FileProcessStatus,
    FileRecord,
    FileStatus,
    Phase,
    ProcessType,
    SubCategory,
    TaskAssignment,
    User,
)
from app.schemas import (
    BucketCountOut,
    ReportsCompletionsOut,
    ReportsDetailOut,
    ReportsDetailRowOut,
    TaxonomyProgressItemOut,
    TaxonomyProgressOut,
)
from app.security import get_current_user, require_admin, user_is_admin
from app.services.reports_export import build_excel_report, build_pdf_report, detail_rows

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _final_process_type_id(db: Session) -> int | None:
    """The last stage by SortOrder (e.g. Render) - a file counts as 'completed'
    for reporting purposes only once this specific stage reaches Complete."""
    return db.scalar(
        select(ProcessType.ProcessTypeID).where(ProcessType.IsActive == True).order_by(ProcessType.SortOrder.desc())  # noqa: E712
    )


def _complete_status_id(db: Session) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == "Complete"))


def _repair_status_id(db: Session) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == "Repair"))


def _revoked_status_id(db: Session) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == "Revoked"))


def _scope_user_id(current_user: User, requested_user_id: int | None) -> int | None:
    """Non-admins always get their own progress report only, regardless of
    what user_id they pass - counts every stage THEY personally completed,
    not just the file's final stage, since 'own worked data' means their own
    tasks, not the org-wide finished-file metric. Admins see the global
    finished-file metric by default, or can pass user_id to inspect one
    specific worker's own report the same way that worker sees it themselves
    (mirrors calendar._scope_user_id's admin-optional-scoping pattern)."""
    if not user_is_admin(current_user):
        return current_user.UserID
    return requested_user_id


def _completions_by_day(
    db: Session,
    complete_id: int,
    start: date_cls,
    end_exclusive: date_cls,
    user_id: int | None = None,
) -> dict:
    """Counts every stage-completion (Polish/GLB/Render, whoever did it) on
    each day - this is a 'how much work got done' activity metric, matching
    what each worker's own report already counts, so the team-wide total is
    just the sum of everyone's individual activity rather than a separate,
    stricter 'fully finished the whole pipeline' metric (that one lives in
    taxonomy-progress's isFullyCompleted instead)."""
    query = select(cast(FileProcessStatus.CompletionTS, Date), func.count()).where(
        FileProcessStatus.StatusID == complete_id,
        FileProcessStatus.CompletionTS >= start,
        FileProcessStatus.CompletionTS < end_exclusive,
    )
    if user_id is not None:
        query = query.where(FileProcessStatus.AssignedToUserID == user_id)
    query = query.group_by(cast(FileProcessStatus.CompletionTS, Date))
    return dict(db.execute(query).all())


def _repairs_by_day(
    db: Session,
    repair_id: int | None,
    start: date_cls,
    end_exclusive: date_cls,
    user_id: int | None = None,
) -> dict:
    """Repair must be sourced from TaskAssignment, not FileProcessStatus - a
    reject never touches FileProcessStatus.CompletionTS (the stage moves
    Submitted -> Repair -> a fresh Pending, none of which sets it). Mirrors
    why calendar.py's failed_q is TaskAssignment-based for the same reason:
    Fail/Repair are attempt-level events, not stage-level "current state"
    facts the way Complete is. Revoked assignments (admin data-entry mistakes)
    are excluded from repair counts."""
    if repair_id is None:
        return {}
    revoked_id = db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == "Revoked"))
    query = select(cast(TaskAssignment.CompletionTS, Date), func.count()).where(
        TaskAssignment.StatusID == repair_id,
        TaskAssignment.CompletionTS >= start,
        TaskAssignment.CompletionTS < end_exclusive,
        TaskAssignment.StatusID != revoked_id,
    )
    if user_id is not None:
        query = query.where(TaskAssignment.AssignedToUserID == user_id)
    query = query.group_by(cast(TaskAssignment.CompletionTS, Date))
    return dict(db.execute(query).all())


def _daily_series(day_counts: dict, start: date_cls, end_inclusive: date_cls) -> list[BucketCountOut]:
    """One bucket per day across the whole [start, end_inclusive] range - the
    Report View always shows the exact range, never a fixed week/month/year
    shape around a single reference point."""
    days = (end_inclusive - start).days + 1
    buckets = []
    for i in range(days):
        d = start + timedelta(days=i)
        buckets.append(BucketCountOut(label=d.strftime("%b %d"), date=d.isoformat(), count=day_counts.get(d, 0)))
    return buckets


def _previous_period(start: date_cls, end_inclusive: date_cls) -> tuple[date_cls, date_cls]:
    """The immediately-preceding period of equal length, for the comparison
    bucket - e.g. selecting Jan 8-14 compares against Jan 1-7."""
    period_len = (end_inclusive - start).days + 1
    prev_end_inclusive = start - timedelta(days=1)
    prev_start = prev_end_inclusive - timedelta(days=period_len - 1)
    return prev_start, prev_end_inclusive


def _process_type_breakdown(
    db: Session, status_id: int | None, start: date_cls, end_exclusive: date_cls, user_id: int | None, *, source
) -> list[BucketCountOut]:
    """Completions are sourced from FileProcessStatus, Repairs from
    TaskAssignment - same split as _completions_by_day/_repairs_by_day above,
    for the same reason (a reject never touches FileProcessStatus).
    Revoked assignments (admin data-entry mistakes) are excluded from TaskAssignment queries."""
    if status_id is None:
        return []
    revoked_id = db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == "Revoked"))
    query = (
        select(ProcessType.ProcessTypeName, func.count())
        .select_from(source)
        .join(ProcessType, ProcessType.ProcessTypeID == source.ProcessTypeID)
        .where(source.StatusID == status_id, source.CompletionTS >= start, source.CompletionTS < end_exclusive)
        .group_by(ProcessType.ProcessTypeName)
    )
    # Exclude revoked assignments when querying TaskAssignment (repairs/failures)
    if source is TaskAssignment:
        query = query.where(source.StatusID != revoked_id)
    if user_id is not None:
        query = query.where(source.AssignedToUserID == user_id)
    return [BucketCountOut(label=name, count=count) for name, count in db.execute(query).all()]


def _build_range_report(
    start: date_cls,
    end_inclusive: date_cls,
    day_counts: dict,
    prev_total: int,
    breakdown: list[BucketCountOut],
) -> ReportsCompletionsOut:
    """Shared response shape for /completions and /repairs - a daily series
    across the chosen range, a 2-bucket comparison against the immediately
    preceding period of equal length, and a process-type breakdown."""
    series = _daily_series(day_counts, start, end_inclusive)
    total_in_range = sum(b.count for b in series)
    prev_start, _prev_end = _previous_period(start, end_inclusive)

    comparison = [
        BucketCountOut(label="Previous period", date=prev_start.isoformat(), count=prev_total),
        BucketCountOut(label="Selected range", date=start.isoformat(), count=total_in_range),
    ]

    return ReportsCompletionsOut(
        startDate=start.isoformat(),
        endDate=end_inclusive.isoformat(),
        totalInRange=total_in_range,
        series=series,
        comparison=comparison,
        processTypeBreakdown=breakdown,
    )


def _parse_range(start_date: str, end_date: str) -> tuple[date_cls, date_cls]:
    start = date_cls.fromisoformat(start_date)
    end_inclusive = date_cls.fromisoformat(end_date)
    if end_inclusive < start:
        raise HTTPException(status_code=400, detail="end_date must not be before start_date")
    return start, end_inclusive


@router.get("/completions", response_model=ReportsCompletionsOut)
def get_completions(
    start_date: str,
    end_date: str,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end_inclusive = _parse_range(start_date, end_date)
    end_exclusive = end_inclusive + timedelta(days=1)
    complete_id = _complete_status_id(db)
    scoped_user_id = _scope_user_id(current_user, user_id)

    day_counts = _completions_by_day(db, complete_id, start, end_exclusive, scoped_user_id)
    prev_start, prev_end_inclusive = _previous_period(start, end_inclusive)
    prev_day_counts = _completions_by_day(db, complete_id, prev_start, prev_end_inclusive + timedelta(days=1), scoped_user_id)
    breakdown = _process_type_breakdown(db, complete_id, start, end_exclusive, scoped_user_id, source=FileProcessStatus)

    return _build_range_report(start, end_inclusive, day_counts, sum(prev_day_counts.values()), breakdown)


@router.get("/repairs", response_model=ReportsCompletionsOut)
def get_repairs(
    start_date: str,
    end_date: str,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sibling of /completions tracking admin-rejected ('Repair') attempts
    instead of Complete ones - same shape, same scoping rule, so the
    frontend can render it with the exact same chart components."""
    start, end_inclusive = _parse_range(start_date, end_date)
    end_exclusive = end_inclusive + timedelta(days=1)
    repair_id = _repair_status_id(db)
    scoped_user_id = _scope_user_id(current_user, user_id)

    day_counts = _repairs_by_day(db, repair_id, start, end_exclusive, scoped_user_id)
    prev_start, prev_end_inclusive = _previous_period(start, end_inclusive)
    prev_day_counts = _repairs_by_day(db, repair_id, prev_start, prev_end_inclusive + timedelta(days=1), scoped_user_id)
    breakdown = _process_type_breakdown(db, repair_id, start, end_exclusive, scoped_user_id, source=TaskAssignment)

    return _build_range_report(start, end_inclusive, day_counts, sum(prev_day_counts.values()), breakdown)


def _progress_items(id_to_name: dict, id_to_total: dict, id_to_completed: dict) -> list[TaxonomyProgressItemOut]:
    items = []
    for id_, name in id_to_name.items():
        total = id_to_total.get(id_, 0)
        completed = id_to_completed.get(id_, 0)
        pct = round((completed / total) * 100, 1) if total else 0.0
        items.append(
            TaxonomyProgressItemOut(
                id=id_,
                name=name,
                totalFiles=total,
                completedFiles=completed,
                completionPct=pct,
                isFullyCompleted=total > 0 and completed == total,
            )
        )
    return items


@router.get("/taxonomy-progress", response_model=TaxonomyProgressOut)
def get_taxonomy_progress(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    final_pt_id = _final_process_type_id(db)
    complete_id = _complete_status_id(db)

    completed_ids_subq = (
        select(FileProcessStatus.FileID).where(
            FileProcessStatus.ProcessTypeID == final_pt_id, FileProcessStatus.StatusID == complete_id
        )
        if final_pt_id is not None
        else None
    )

    def completed_filter(query):
        if completed_ids_subq is None:
            return query.where(false())
        return query.where(FileRecord.FileID.in_(completed_ids_subq))

    phase_name_by_id = {p.PhaseID: p.PhaseName for p in db.scalars(select(Phase))}
    total_by_phase = dict(
        db.execute(select(FileRecord.PhaseID, func.count()).where(FileRecord.IsActive == True).group_by(FileRecord.PhaseID)).all()  # noqa: E712
    )
    completed_by_phase = dict(
        db.execute(
            completed_filter(select(FileRecord.PhaseID, func.count()).where(FileRecord.IsActive == True)).group_by(  # noqa: E712
                FileRecord.PhaseID
            )
        ).all()
    )
    phases = _progress_items(phase_name_by_id, total_by_phase, completed_by_phase)

    category_name_by_id = {c.CategoryID: c.CategoryName for c in db.scalars(select(Category))}
    total_by_category = dict(
        db.execute(
            select(FileRecord.CategoryID, func.count())
            .where(FileRecord.IsActive == True, FileRecord.CategoryID.isnot(None))  # noqa: E712
            .group_by(FileRecord.CategoryID)
        ).all()
    )
    completed_by_category = dict(
        db.execute(
            completed_filter(
                select(FileRecord.CategoryID, func.count()).where(
                    FileRecord.IsActive == True, FileRecord.CategoryID.isnot(None)  # noqa: E712
                )
            ).group_by(FileRecord.CategoryID)
        ).all()
    )
    categories = _progress_items(category_name_by_id, total_by_category, completed_by_category)

    subcategory_name_by_id = {sc.SubCategoryID: sc.SubCategoryName for sc in db.scalars(select(SubCategory))}
    total_by_subcategory = dict(
        db.execute(
            select(FileRecord.SubCategoryID, func.count())
            .where(FileRecord.IsActive == True, FileRecord.SubCategoryID.isnot(None))  # noqa: E712
            .group_by(FileRecord.SubCategoryID)
        ).all()
    )
    completed_by_subcategory = dict(
        db.execute(
            completed_filter(
                select(FileRecord.SubCategoryID, func.count()).where(
                    FileRecord.IsActive == True, FileRecord.SubCategoryID.isnot(None)  # noqa: E712
                )
            ).group_by(FileRecord.SubCategoryID)
        ).all()
    )
    sub_categories = _progress_items(subcategory_name_by_id, total_by_subcategory, completed_by_subcategory)

    return TaxonomyProgressOut(phases=phases, categories=categories, subCategories=sub_categories)


def _safe_filename_part(label: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in label)


def _resolve_export_target(db: Session, current_user: User, user_id: int | None) -> tuple[int | None, str | None]:
    scoped_user_id = _scope_user_id(current_user, user_id)
    username = None
    if scoped_user_id is not None:
        target = db.get(User, scoped_user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")
        username = target.Username
    return scoped_user_id, username


@router.get("/export/excel")
def export_excel(
    start_date: str,
    end_date: str,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Flat, filterable ledger for the selected range/user - one row per
    process-stage attempt with both its Assigned and Completion timestamp
    (see reports_export.py's detail_rows). The Export popup computes
    start_date/end_date from whichever preset or custom range it used -
    always exactly what was picked there, independent of the Report View."""
    start, end_inclusive = _parse_range(start_date, end_date)
    scoped_user_id, username = _resolve_export_target(db, current_user, user_id)

    content, label = build_excel_report(db, scoped_user_id, username, start, end_inclusive)
    filename = f"completions_{_safe_filename_part(label)}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/pdf")
def export_pdf(
    start_date: str,
    end_date: str,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Self-contained PDF snapshot for the selected range/user - the same
    completions-over-time and per-process-type charts the Reports page shows
    on screen (rendered server-side), plus the full activity ledger."""
    start, end_inclusive = _parse_range(start_date, end_date)
    scoped_user_id, username = _resolve_export_target(db, current_user, user_id)

    content, label = build_pdf_report(db, scoped_user_id, username, start, end_inclusive)
    filename = f"completions_{_safe_filename_part(label)}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/detail", response_model=ReportsDetailOut)
def get_detail(
    start_date: str,
    end_date: str,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Worked-files ledger for the Report View's Worked Files panel - shares
    the same start_date/end_date range as /completions and /repairs (one
    calendar range drives the whole page). One row per assignment attempt in
    the range, same data source as the Excel/PDF exports
    (reports_export.py::detail_rows). Rows left at Repair (not approved) get
    a reassignedTo - the very next assignment for that same
    file+process-type after this attempt (same worker or a different one,
    whichever actually happened)."""
    start, end_inclusive = _parse_range(start_date, end_date)
    end_exclusive = end_inclusive + timedelta(days=1)
    scoped_user_id = _scope_user_id(current_user, user_id)

    rows = detail_rows(db, start, end_exclusive, scoped_user_id)

    # Next-assignment lookup needs the full history per (file, process type),
    # not just what's in this range - a Repair row near the end of the range
    # may have been reassigned only after it closed.
    all_rows = detail_rows(db, date_cls.min, end_exclusive, None)
    next_by_key: dict[tuple[str, str], list[dict]] = {}
    for r in all_rows:
        next_by_key.setdefault((r["file_name"], r["process_type"]), []).append(r)
    for bucket in next_by_key.values():
        bucket.sort(key=lambda r: r["assigned_ts"] or date_cls.min)

    def reassigned_to(row: dict) -> str | None:
        if row["status"] != "Repair":
            return None
        bucket = next_by_key.get((row["file_name"], row["process_type"]), [])
        later = [r for r in bucket if r["assigned_ts"] and row["assigned_ts"] and r["assigned_ts"] > row["assigned_ts"]]
        return later[0]["assigned_to"] if later else None

    return ReportsDetailOut(
        rows=[
            ReportsDetailRowOut(
                fileName=r["file_name"],
                processType=r["process_type"],
                assignedTo=r["assigned_to"],
                status=r["status"],
                assignedTs=r["assigned_ts"],
                completionTs=r["completion_ts"],
                reassignedTo=reassigned_to(r),
            )
            for r in rows
        ]
    )
