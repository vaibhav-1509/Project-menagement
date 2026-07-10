from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, FileRecord, Phase, PhasePath, SubCategory, User
from app.schemas import (
    CategoryAdminOut,
    CreateCategoryRequest,
    CreatePhaseRequest,
    CreateSubCategoryRequest,
    LookupItem,
    PhaseAdminOut,
    SubCategoryAdminOut,
    TaxonomyAdminOut,
    UpdateTaxonomyNodeRequest,
)
from app.security import require_admin

router = APIRouter(prefix="/api/admin", tags=["taxonomy"])


@router.get("/taxonomy", response_model=TaxonomyAdminOut)
def get_taxonomy(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Full Phase/Category/Sub-Category listing for the admin taxonomy panel -
    unlike /api/lookups (active-only, used everywhere else), this includes
    inactive rows too, plus file/user counts, so an admin can see what's safe
    to delete versus what should just be deactivated."""
    phases = db.scalars(select(Phase)).all()
    categories = db.scalars(select(Category)).all()
    sub_categories = db.scalars(select(SubCategory)).all()

    files_per_phase = dict(db.execute(select(FileRecord.PhaseID, func.count()).group_by(FileRecord.PhaseID)).all())
    users_per_phase = dict(db.execute(select(User.PhaseID, func.count()).group_by(User.PhaseID)).all())
    files_per_category = dict(
        db.execute(
            select(FileRecord.CategoryID, func.count()).where(FileRecord.CategoryID.isnot(None)).group_by(FileRecord.CategoryID)
        ).all()
    )
    files_per_subcategory = dict(
        db.execute(
            select(FileRecord.SubCategoryID, func.count())
            .where(FileRecord.SubCategoryID.isnot(None))
            .group_by(FileRecord.SubCategoryID)
        ).all()
    )
    phase_name_by_id = {p.PhaseID: p.PhaseName for p in phases}
    category_by_id = {c.CategoryID: c for c in categories}

    return TaxonomyAdminOut(
        phases=[
            PhaseAdminOut(
                id=p.PhaseID,
                name=p.PhaseName,
                isActive=p.IsActive,
                fileCount=files_per_phase.get(p.PhaseID, 0),
                userCount=users_per_phase.get(p.PhaseID, 0),
            )
            for p in phases
        ],
        categories=[
            CategoryAdminOut(
                id=c.CategoryID,
                phaseId=c.PhaseID,
                phaseName=phase_name_by_id.get(c.PhaseID, f"#{c.PhaseID}"),
                name=c.CategoryName,
                isActive=c.IsActive,
                fileCount=files_per_category.get(c.CategoryID, 0),
            )
            for c in categories
        ],
        subCategories=[
            SubCategoryAdminOut(
                id=sc.SubCategoryID,
                categoryId=sc.CategoryID,
                categoryName=category_by_id[sc.CategoryID].CategoryName if sc.CategoryID in category_by_id else f"#{sc.CategoryID}",
                phaseId=category_by_id[sc.CategoryID].PhaseID if sc.CategoryID in category_by_id else 0,
                phaseName=phase_name_by_id.get(category_by_id[sc.CategoryID].PhaseID, "") if sc.CategoryID in category_by_id else "",
                name=sc.SubCategoryName,
                isActive=sc.IsActive,
                fileCount=files_per_subcategory.get(sc.SubCategoryID, 0),
            )
            for sc in sub_categories
        ],
    )


@router.post("/phases", response_model=LookupItem, status_code=201)
def create_phase(
    request: CreatePhaseRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    phase = Phase(PhaseName=request.name)
    db.add(phase)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="A phase with that name already exists") from exc
    db.refresh(phase)
    return LookupItem(id=phase.PhaseID, name=phase.PhaseName)


@router.patch("/phases/{phase_id}")
def update_phase(
    phase_id: int,
    request: UpdateTaxonomyNodeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    phase = db.get(Phase, phase_id)
    if phase is None:
        raise HTTPException(status_code=404, detail="Phase not found")
    if request.name is not None:
        name = request.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be blank")
        phase.PhaseName = name
    if request.is_active is not None:
        phase.IsActive = request.is_active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="A phase with that name already exists") from exc
    return {"id": phase.PhaseID, "name": phase.PhaseName, "isActive": phase.IsActive}


@router.delete("/phases/{phase_id}")
def delete_phase(
    phase_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    phase = db.get(Phase, phase_id)
    if phase is None:
        raise HTTPException(status_code=404, detail="Phase not found")

    blockers = []
    if db.scalar(select(FileRecord.FileID).where(FileRecord.PhaseID == phase_id)) is not None:
        blockers.append("files")
    if db.scalar(select(User.UserID).where(User.PhaseID == phase_id)) is not None:
        blockers.append("users")
    if db.scalar(select(Category.CategoryID).where(Category.PhaseID == phase_id)) is not None:
        blockers.append("categories")
    if db.scalar(select(PhasePath.PhasePathID).where(PhasePath.PhaseID == phase_id)) is not None:
        blockers.append("a configured folder path")
    if blockers:
        raise HTTPException(status_code=400, detail=f"Cannot delete - still referenced by: {', '.join(blockers)}")

    db.delete(phase)
    db.commit()
    return {"status": "deleted"}


@router.post("/categories", status_code=201)
def create_category(
    request: CreateCategoryRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.get(Phase, request.phase_id) is None:
        raise HTTPException(status_code=400, detail="Unknown phase")

    category = Category(PhaseID=request.phase_id, CategoryName=request.name)
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="That category already exists in this phase") from exc
    db.refresh(category)
    return {"id": category.CategoryID, "phaseId": category.PhaseID, "name": category.CategoryName}


@router.patch("/categories/{category_id}")
def update_category(
    category_id: int,
    request: UpdateTaxonomyNodeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if request.name is not None:
        name = request.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be blank")
        category.CategoryName = name
    if request.is_active is not None:
        category.IsActive = request.is_active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="That category already exists in this phase") from exc
    return {"id": category.CategoryID, "name": category.CategoryName, "isActive": category.IsActive}


@router.delete("/categories/{category_id}")
def delete_category(
    category_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    in_use = db.scalar(select(FileRecord.FileID).where(FileRecord.CategoryID == category_id))
    if in_use is not None:
        raise HTTPException(status_code=400, detail="Cannot delete - one or more files use this category")

    db.execute(SubCategory.__table__.delete().where(SubCategory.CategoryID == category_id))
    db.delete(category)
    db.commit()
    return {"status": "deleted"}


@router.post("/subcategories", status_code=201)
def create_subcategory(
    request: CreateSubCategoryRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.get(Category, request.category_id) is None:
        raise HTTPException(status_code=400, detail="Unknown category")

    sub_category = SubCategory(CategoryID=request.category_id, SubCategoryName=request.name)
    db.add(sub_category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="That sub-category already exists in this category") from exc
    db.refresh(sub_category)
    return {"id": sub_category.SubCategoryID, "categoryId": sub_category.CategoryID, "name": sub_category.SubCategoryName}


@router.patch("/subcategories/{sub_category_id}")
def update_subcategory(
    sub_category_id: int,
    request: UpdateTaxonomyNodeRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sub_category = db.get(SubCategory, sub_category_id)
    if sub_category is None:
        raise HTTPException(status_code=404, detail="Sub-category not found")
    if request.name is not None:
        name = request.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name cannot be blank")
        sub_category.SubCategoryName = name
    if request.is_active is not None:
        sub_category.IsActive = request.is_active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="That sub-category already exists in this category") from exc
    return {"id": sub_category.SubCategoryID, "name": sub_category.SubCategoryName, "isActive": sub_category.IsActive}


@router.delete("/subcategories/{sub_category_id}")
def delete_subcategory(
    sub_category_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sub_category = db.get(SubCategory, sub_category_id)
    if sub_category is None:
        raise HTTPException(status_code=404, detail="Sub-category not found")

    in_use = db.scalar(select(FileRecord.FileID).where(FileRecord.SubCategoryID == sub_category_id))
    if in_use is not None:
        raise HTTPException(status_code=400, detail="Cannot delete - one or more files use this sub-category")

    db.delete(sub_category)
    db.commit()
    return {"status": "deleted"}
