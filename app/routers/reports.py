import calendar as calendar_module
from datetime import date as date_cls, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import Date, cast, false, func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, FileProcessStatus, FileRecord, FileStatus, Phase, ProcessType, SubCategory, User
from app.schemas import (
    BucketCountOut,
    MonthSeriesOut,
    ReportsCompletionsOut,
    ReportsTotalsOut,
    TaxonomyProgressItemOut,
    TaxonomyProgressOut,
    WeekSeriesOut,
    YearSeriesOut,
)
from app.security import get_current_user, require_admin, user_is_admin
from app.services.reports_export import RANGE_CHOICES, build_excel_report, build_pdf_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _final_process_type_id(db: Session) -> int | None:
    """The last stage by SortOrder (e.g. Render) - a file counts as 'completed'
    for reporting purposes only once this specific stage reaches Complete."""
    return db.scalar(
        select(ProcessType.ProcessTypeID).where(ProcessType.IsActive == True).order_by(ProcessType.SortOrder.desc())  # noqa: E712
    )


def _complete_status_id(db: Session) -> int:
    return db.scalar(select(FileStatus.StatusID).where(FileStatus.StatusName == "Complete"))


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


@router.get("/completions", response_model=ReportsCompletionsOut)
def get_completions(
    reference_date: str | None = None,
    compare_weeks: int = 4,
    compare_months: int = 6,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ref = date_cls.fromisoformat(reference_date) if reference_date else date_cls.today()
    complete_id = _complete_status_id(db)
    scoped_user_id = _scope_user_id(current_user, user_id)

    # One grouped query wide enough to cover the year view plus both
    # comparison windows, instead of several overlapping range queries.
    window_days = max(400, compare_months * 31 + 31, compare_weeks * 7 + 7)
    window_start = ref - timedelta(days=window_days)
    window_end_exclusive = ref + timedelta(days=1)
    day_counts = _completions_by_day(db, complete_id, window_start, window_end_exclusive, scoped_user_id)

    def count_on(d: date_cls) -> int:
        return day_counts.get(d, 0)

    monday = ref - timedelta(days=ref.weekday())
    week_dates = [monday + timedelta(days=i) for i in range(7)]
    week = WeekSeriesOut(
        days=[
            BucketCountOut(label=WEEKDAY_LABELS[i], date=d.isoformat(), count=count_on(d))
            for i, d in enumerate(week_dates)
        ]
    )

    days_in_month = calendar_module.monthrange(ref.year, ref.month)[1]
    month_dates = [date_cls(ref.year, ref.month, day_num) for day_num in range(1, days_in_month + 1)]
    month = MonthSeriesOut(
        days=[BucketCountOut(label=str(d.day), date=d.isoformat(), count=count_on(d)) for d in month_dates]
    )

    year_months = []
    for m in range(1, 13):
        days_in_m = calendar_module.monthrange(ref.year, m)[1]
        total = sum(count_on(date_cls(ref.year, m, d)) for d in range(1, days_in_m + 1))
        year_months.append(BucketCountOut(label=MONTH_LABELS[m - 1], date=f"{ref.year}-{m:02d}", count=total))
    year = YearSeriesOut(months=year_months)

    week_comparison = []
    for i in range(compare_weeks - 1, -1, -1):
        week_monday = monday - timedelta(days=7 * i)
        total = sum(count_on(week_monday + timedelta(days=d)) for d in range(7))
        label = f"{week_monday.strftime('%b %d')}" if i > 0 else "This week"
        week_comparison.append(BucketCountOut(label=label, date=week_monday.isoformat(), count=total))

    month_comparison = []
    for i in range(compare_months - 1, -1, -1):
        m_year, m_month = ref.year, ref.month - i
        while m_month < 1:
            m_month += 12
            m_year -= 1
        days_in_m = calendar_module.monthrange(m_year, m_month)[1]
        total = sum(count_on(date_cls(m_year, m_month, d)) for d in range(1, days_in_m + 1))
        label = f"{MONTH_LABELS[m_month - 1]} {m_year}" if i > 0 else "This month"
        month_comparison.append(BucketCountOut(label=label, date=f"{m_year}-{m_month:02d}", count=total))

    totals = ReportsTotalsOut(
        today=count_on(ref),
        thisWeek=sum(b.count for b in week.days),
        thisMonth=sum(b.count for b in month.days),
        thisYear=sum(b.count for b in year.months),
    )

    return ReportsCompletionsOut(
        referenceDate=ref.isoformat(),
        totals=totals,
        week=week,
        month=month,
        year=year,
        weekComparison=week_comparison,
        monthComparison=month_comparison,
    )


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


def _resolve_export_target(db: Session, current_user: User, range_key: str, user_id: int | None) -> tuple[int | None, str | None]:
    if range_key not in RANGE_CHOICES:
        raise HTTPException(status_code=400, detail=f"range must be one of {', '.join(RANGE_CHOICES)}")
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
    range: str = "month",
    reference_date: str | None = None,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Flat, filterable ledger for the selected range/user - one row per
    process-stage attempt with both its Assigned and Completion timestamp
    (see reports_export.py's _detail_rows)."""
    ref = date_cls.fromisoformat(reference_date) if reference_date else date_cls.today()
    scoped_user_id, username = _resolve_export_target(db, current_user, range, user_id)

    content, label = build_excel_report(db, scoped_user_id, username, range, ref)
    filename = f"completions_{_safe_filename_part(label)}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/pdf")
def export_pdf(
    range: str = "month",
    reference_date: str | None = None,
    user_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Self-contained PDF snapshot for the selected range/user - the same
    completions-over-time and per-process-type charts the Reports page shows
    on screen (rendered server-side), plus the full activity ledger."""
    ref = date_cls.fromisoformat(reference_date) if reference_date else date_cls.today()
    scoped_user_id, username = _resolve_export_target(db, current_user, range, user_id)

    content, label = build_pdf_report(db, scoped_user_id, username, range, ref)
    filename = f"completions_{_safe_filename_part(label)}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
