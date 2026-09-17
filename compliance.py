"""
Computes the PRD's CMP-00x compliance checks LIVE from existing Project/Payment/Financial/
Progress data -- deliberately NOT writing to the existing (but currently unpopulated)
ComplianceCheck table. Nothing in the risk engine or anywhere else ever computes these checks
today, so retrofitting risk_engine.py to persist them is a bigger change than this pass calls
for; these are cheap boolean/comparison checks over data already loaded, safe to compute on
every request.

Only implements the checks answerable from fields that actually exist on Project/Payment/
ProjectFinancial/ProjectProgress -- CMP checks that would need data the schema doesn't carry
(e.g. checks against an external sanction-order document) are not fabricated here.
"""
from datetime import date


def evaluate_compliance(project, latest_financial, latest_progress, payments: list) -> list[dict]:
    results = []

    if project.estimated_cost:
        tolerance_amount = float(project.estimated_cost) * 1.1
        if float(project.sanctioned_amount) > tolerance_amount:
            results.append({
                "check_code": "CMP-001", "result": "WARNING",
                "evidence": {
                    "sanctioned_amount": float(project.sanctioned_amount),
                    "estimated_cost": float(project.estimated_cost),
                    "tolerance_percent": 10,
                },
            })
        else:
            results.append({"check_code": "CMP-001", "result": "PASS", "evidence": {}})

    if latest_financial:
        if float(latest_financial.utilized_amount) > float(project.sanctioned_amount):
            results.append({
                "check_code": "CMP-002", "result": "FAIL",
                "evidence": {
                    "utilized_amount": float(latest_financial.utilized_amount),
                    "sanctioned_amount": float(project.sanctioned_amount),
                },
            })
        else:
            results.append({"check_code": "CMP-002", "result": "PASS", "evidence": {}})

    if project.expected_completion_date:
        if project.expected_completion_date < project.sanction_date:
            results.append({
                "check_code": "CMP-003", "result": "FAIL",
                "evidence": {
                    "expected_completion_date": project.expected_completion_date.isoformat(),
                    "sanction_date": project.sanction_date.isoformat(),
                },
            })
        else:
            results.append({"check_code": "CMP-003", "result": "PASS", "evidence": {}})

    if project.actual_completion_date:
        if project.actual_completion_date < project.sanction_date:
            results.append({
                "check_code": "CMP-004", "result": "FAIL",
                "evidence": {
                    "actual_completion_date": project.actual_completion_date.isoformat(),
                    "sanction_date": project.sanction_date.isoformat(),
                },
            })
        else:
            results.append({"check_code": "CMP-004", "result": "PASS", "evidence": {}})

    if payments:
        pre_sanction = [p for p in payments if p.payment_date < project.sanction_date]
        if pre_sanction:
            results.append({
                "check_code": "CMP-005", "result": "FAIL",
                "evidence": {
                    "pre_sanction_payment_count": len(pre_sanction),
                    "earliest_payment_date": min(p.payment_date for p in pre_sanction).isoformat(),
                    "sanction_date": project.sanction_date.isoformat(),
                },
            })
        else:
            results.append({"check_code": "CMP-005", "result": "PASS", "evidence": {}})

    if project.status.value == "completed":
        progress = latest_progress.physical_progress_percent if latest_progress else 0
        if progress < 100:
            results.append({
                "check_code": "CMP-006", "result": "WARNING",
                "evidence": {"status": "completed", "physical_progress_percent": progress},
            })
        else:
            results.append({"check_code": "CMP-006", "result": "PASS", "evidence": {}})

    if project.location_id is None or not project.location or project.location.latitude is None or project.location.longitude is None:
        results.append({"check_code": "CMP-007", "result": "WARNING", "evidence": {"has_coordinates": False}})
    else:
        results.append({"check_code": "CMP-007", "result": "PASS", "evidence": {}})

    return results
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
