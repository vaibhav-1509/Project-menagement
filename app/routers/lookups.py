from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, FileStatus, Phase, ProcessType, Role, SubCategory, User
from app.schemas import CategoryLookupItem, LookupItem, LookupsOut, SubCategoryLookupItem
from app.security import get_current_user

router = APIRouter(prefix="/api/lookups", tags=["lookups"])


@router.get("", response_model=LookupsOut)
def get_lookups(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Id -> name tables the frontend needs to render Phase/Status/Category
    columns and filter dropdowns without duplicating this data on every file row.
    Roles are included too (used by the admin-only User Management page) -
    role names aren't sensitive, so this stays on the one shared endpoint.

    Phases/Categories/Sub-Categories are filtered to IsActive=1 - deactivating
    one (see /api/admin/taxonomy) hides it from every dropdown that reads this
    endpoint without needing per-component changes. Existing files/users can
    still reference an inactive one; they just render as "#id" instead of a
    name in that edge case, which is an acceptable degrade for now."""
    phases = db.scalars(select(Phase).where(Phase.IsActive == True)).all()  # noqa: E712
    statuses = db.scalars(select(FileStatus)).all()
    categories = db.scalars(select(Category).where(Category.IsActive == True)).all()  # noqa: E712
    sub_categories = db.scalars(select(SubCategory).where(SubCategory.IsActive == True)).all()  # noqa: E712
    roles = db.scalars(select(Role)).all()
    process_types = db.scalars(select(ProcessType).where(ProcessType.IsActive == True).order_by(ProcessType.SortOrder)).all()  # noqa: E712

    return LookupsOut(
        phases=[LookupItem(id=p.PhaseID, name=p.PhaseName) for p in phases],
        statuses=[LookupItem(id=s.StatusID, name=s.StatusName) for s in statuses],
        categories=[CategoryLookupItem(id=c.CategoryID, phaseId=c.PhaseID, name=c.CategoryName) for c in categories],
        subCategories=[
            SubCategoryLookupItem(id=sc.SubCategoryID, categoryId=sc.CategoryID, name=sc.SubCategoryName)
            for sc in sub_categories
        ],
        roles=[LookupItem(id=r.RoleID, name=r.RoleName) for r in roles],
        processTypes=[LookupItem(id=pt.ProcessTypeID, name=pt.ProcessTypeName) for pt in process_types],
    )
