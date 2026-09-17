from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, RoleName, Project, Location, RiskScore
from app.schemas.risk import ProjectListItem

router = APIRouter(prefix="/projects", tags=["projects"])

_SORTABLE = {
    "final_score": None,  # handled after the risk-score join below -- can't sort in SQL easily
    "sanctioned_amount": Project.sanctioned_amount,
    "sanction_date": Project.sanction_date,
    "project_code": Project.project_code,
    "created_at": Project.created_at,
}


@router.get("", response_model=list[ProjectListItem])
def list_projects(
    response: Response,
    state: str | None = None,
    district: str | None = None,
    work_type: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    risk_level: str | None = None,
    search: str | None = None,  # matches project_code or title, case-insensitive substring
    ids: str | None = None,  # comma-separated project IDs -- lets a caller resolve specific projects by id
    sort_by: str = Query("created_at", pattern="^(final_score|sanctioned_amount|sanction_date|project_code|created_at)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, le=200),
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Scoped per PRD: national-role users see everything; state/district-scoped users only see
    their own state/district automatically (not just when they pass a filter -- scope is
    enforced server-side regardless of what the client asks for).

    Total row count (post-filter, pre-pagination) is returned via the X-Total-Count header
    rather than changing the response body shape -- several existing pages already depend on
    this endpoint returning a bare array, and breaking that would be exactly the kind of
    "rewrite working functionality" this pass is supposed to avoid.
    """
    q = db.query(Project).options(joinedload(Project.location))
    location_joined = False

    def ensure_location_join(query):
        nonlocal location_joined
        if not location_joined:
            query = query.join(Location, Project.location_id == Location.id)
            location_joined = True
        return query

    user_role_names = {r.role_name for r in current_user.roles}
    is_national = bool(user_role_names & {RoleName.SYSTEM_ADMIN, RoleName.MINISTRY_ADMIN, RoleName.AUDITOR})

    if not is_national:
        state_scopes = [s.scope_value for s in current_user.scopes if s.scope_level.value == "state"]
        district_scopes = [s.scope_value for s in current_user.scopes if s.scope_level.value == "district"]
        if district_scopes:
            q = ensure_location_join(q)
            q = q.filter(Location.district.in_(district_scopes))
        elif state_scopes:
            q = ensure_location_join(q)
            q = q.filter(Location.state.in_(state_scopes))
        else:
            response.headers["X-Total-Count"] = "0"
            return []  # no matching scope at all -- fail closed, not open

    if state:
        q = ensure_location_join(q)
        q = q.filter(Location.state == state)
    if district:
        q = ensure_location_join(q)
        q = q.filter(Location.district == district)
    if work_type:
        q = q.filter(Project.work_type == work_type)
    if status_filter:
        q = q.filter(Project.status == status_filter)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Project.project_code.ilike(like), Project.title.ilike(like)))
    if ids:
        id_list = [i.strip() for i in ids.split(",") if i.strip()]
        if id_list:
            q = q.filter(Project.id.in_(id_list))

    # risk_level can't be applied in SQL here (RiskScore isn't joined -- it's resolved to
    # "latest score per project" in Python below, same as before this change), so it's
    # applied as a post-filter once scores are attached, right before pagination.

    sort_col = _SORTABLE.get(sort_by)
    if sort_col is not None:
        q = q.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    else:
        q = q.order_by(Project.created_at.desc())  # final_score sort applied in Python below

    all_matching = q.all()

    # Latest risk score per project, in one query rather than N+1 -- keyed by project_id.
    all_ids = [p.id for p in all_matching]
    latest_scores = {}
    if all_ids:
        all_scores = (
            db.query(RiskScore)
            .filter(RiskScore.project_id.in_(all_ids))
            .order_by(RiskScore.project_id, RiskScore.created_at.desc())
            .all()
        )
        for s in all_scores:
            if s.project_id not in latest_scores:  # first row per project_id is the newest, thanks to ORDER BY
                latest_scores[s.project_id] = s

    if risk_level:
        all_matching = [p for p in all_matching if p.id in latest_scores and latest_scores[p.id].risk_level.value == risk_level]

    if sort_by == "final_score":
        all_matching.sort(
            key=lambda p: latest_scores[p.id].final_score if p.id in latest_scores else -1,
            reverse=(sort_dir == "desc"),
        )

    response.headers["X-Total-Count"] = str(len(all_matching))
    projects = all_matching[offset: offset + limit]

    return [
        ProjectListItem(
            id=p.id, project_code=p.project_code, title=p.title, work_type=p.work_type,
            status=p.status.value, sanctioned_amount=float(p.sanctioned_amount),
            sanction_date=p.sanction_date,
            state=p.location.state if p.location else None,
            district=p.location.district if p.location else None,
            latitude=p.location.latitude if p.location else None,
            longitude=p.location.longitude if p.location else None,
            risk_level=latest_scores[p.id].risk_level.value if p.id in latest_scores else None,
            final_score=latest_scores[p.id].final_score if p.id in latest_scores else None,
        )
        for p in projects
    ]
