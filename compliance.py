"""
GET /compliance -- cross-project view for the Compliance Center page. Reuses the same
live-computed CMP-00x checks as GET /projects/{id}/compliance (app/services/compliance.py),
just run across every project the caller can see instead of one. Still writes nothing to the
ComplianceCheck table -- see that module's docstring for why.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, RoleName, Project, Location
from app.schemas.risk import ComplianceResultOut
from app.services.compliance import evaluate_compliance

router = APIRouter(prefix="/compliance", tags=["compliance"])


def _scoped_projects(db: Session, user: User):
    q = (
        db.query(Project)
        .options(
            selectinload(Project.location), selectinload(Project.financials),
            selectinload(Project.progress_reports), selectinload(Project.payments),
        )
        .join(Location, Project.location_id == Location.id)
    )
    user_role_names = {r.role_name for r in user.roles}
    is_national = bool(user_role_names & {RoleName.SYSTEM_ADMIN, RoleName.MINISTRY_ADMIN, RoleName.AUDITOR})
    if not is_national:
        district_scopes = [s.scope_value for s in user.scopes if s.scope_level.value == "district"]
        state_scopes = [s.scope_value for s in user.scopes if s.scope_level.value == "state"]
        if district_scopes:
            q = q.filter(Location.district.in_(district_scopes))
        elif state_scopes:
            q = q.filter(Location.state.in_(state_scopes))
        else:
            return []
    return q.all()


@router.get("", response_model=list[ComplianceResultOut])
def list_compliance_results(
    result: str | None = Query(None, pattern="^(PASS|WARNING|FAIL)$"),
    limit: int = Query(200, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Defaults to no filter (all results) if `result` isn't passed. Pass result=WARNING or
    result=FAIL from the frontend to focus on what actually needs review -- PASS rows are the
    majority and mostly just confirm nothing is wrong."""
    projects = _scoped_projects(db, current_user)

    out = []
    for project in projects:
        latest_financial = max(project.financials, key=lambda f: f.as_of_date, default=None)
        latest_progress = max(project.progress_reports, key=lambda pr: pr.report_date, default=None)
        checks = evaluate_compliance(project, latest_financial, latest_progress, list(project.payments))
        for c in checks:
            if result and c["result"] != result:
                continue
            out.append(ComplianceResultOut(project_id=project.id, project_code=project.project_code, **c))
            if len(out) >= limit:
                return out
    return out
