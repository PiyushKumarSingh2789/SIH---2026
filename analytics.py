"""
GET /analytics/summary -- was in the PRD's original API list (Section 24 / Section 7 of the
unified spec) but never implemented until now. Computes portfolio-wide totals via SQL aggregation
(SUM/COUNT), not by fetching every project row to the client -- correct at 1,500+ projects, where
paging through /projects to compute totals client-side would be both slow and silently wrong
(the client only ever sees a page at a time).

Scoped identically to /projects: national roles see everything, state/district-scoped roles only
see their own aggregates.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User, RoleName, Project, Location, ProjectFinancial, RiskScore, RiskRun

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _scoped_project_query(db: Session, user: User):
    q = db.query(Project).join(Location, Project.location_id == Location.id)
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
            return None  # fail closed
    return q


@router.get("/summary")
def get_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base_q = _scoped_project_query(db, current_user)
    if base_q is None:
        return {
            "total_projects": 0, "total_sanctioned_amount": 0, "total_utilized_amount": 0,
            "risk_level_counts": {"critical": 0, "high": 0, "medium": 0, "low": 0, "unscored": 0},
            "status_counts": {}, "state_breakdown": [], "last_risk_run_at": None,
        }

    project_ids = [p.id for p in base_q.all()]
    total_projects = len(project_ids)

    total_sanctioned = (
        db.query(func.sum(Project.sanctioned_amount)).filter(Project.id.in_(project_ids)).scalar() or 0
    ) if project_ids else 0

    # Latest utilized_amount per project, summed -- utilization history is append-only (see
    # ProjectFinancial model), so we need each project's most recent row, not a naive SUM of all rows.
    total_utilized = 0
    if project_ids:
        latest_financials = (
            db.query(ProjectFinancial)
            .filter(ProjectFinancial.project_id.in_(project_ids))
            .order_by(ProjectFinancial.project_id, ProjectFinancial.as_of_date.desc())
            .all()
        )
        seen = set()
        for f in latest_financials:
            if f.project_id not in seen:
                seen.add(f.project_id)
                total_utilized += float(f.utilized_amount)

    status_counts = {}
    if project_ids:
        rows = (
            db.query(Project.status, func.count(Project.id))
            .filter(Project.id.in_(project_ids)).group_by(Project.status).all()
        )
        status_counts = {s.value: c for s, c in rows}

    # State breakdown for Portfolio Analytics -- project count + sanctioned total per state,
    # scoped identically to everything above. A state-scoped user only ever has one state in
    # their own aggregate anyway; this is mainly useful for national roles comparing states.
    state_breakdown = []
    if project_ids:
        rows = (
            db.query(Location.state, func.count(Project.id), func.sum(Project.sanctioned_amount))
            .join(Location, Project.location_id == Location.id)
            .filter(Project.id.in_(project_ids))
            .group_by(Location.state)
            .order_by(func.count(Project.id).desc())
            .all()
        )
        state_breakdown = [
            {"state": state, "project_count": count, "total_sanctioned_amount": float(total or 0)}
            for state, count, total in rows
        ]

    risk_level_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unscored": 0}
    last_run = db.query(RiskRun).order_by(RiskRun.created_at.desc()).first()
    if last_run and project_ids:
        rows = (
            db.query(RiskScore.risk_level, func.count(RiskScore.id))
            .filter(RiskScore.risk_run_id == last_run.id, RiskScore.project_id.in_(project_ids))
            .group_by(RiskScore.risk_level).all()
        )
        for level, count in rows:
            risk_level_counts[level.value] = count
        scored_count = sum(risk_level_counts.values())
        risk_level_counts["unscored"] = max(0, total_projects - scored_count)
    else:
        risk_level_counts["unscored"] = total_projects

    return {
        "total_projects": total_projects,
        "total_sanctioned_amount": float(total_sanctioned),
        "total_utilized_amount": total_utilized,
        "risk_level_counts": risk_level_counts,
        "status_counts": status_counts,
        "state_breakdown": state_breakdown,
        "last_risk_run_at": last_run.created_at.isoformat() if last_run else None,
    }
