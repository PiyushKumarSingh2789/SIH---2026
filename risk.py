from datetime import date, datetime
from pydantic import BaseModel


class ProjectListItem(BaseModel):
    id: str
    project_code: str
    title: str
    work_type: str
    status: str
    sanctioned_amount: float
    sanction_date: date
    state: str | None
    district: str | None
    latitude: float | None = None
    longitude: float | None = None
    risk_level: str | None = None
    final_score: float | None = None


class FactorResultOut(BaseModel):
    factor_code: str
    raw_value: float | None
    normalized_score: float
    weight: float
    contribution: float
    evidence: dict
    explanation: str
    detector_version: str

    model_config = {"from_attributes": True}


class RiskScoreOut(BaseModel):
    project_id: str
    project_code: str
    final_score: float
    risk_level: str
    factors_computed_count: int
    evidence_completeness_percent: float
    risk_run_id: str
    engine_version: str
    factors: list[FactorResultOut]


class RiskRunOut(BaseModel):
    id: str
    engine_version: str
    started_at: datetime
    completed_at: datetime | None
    project_count: int

    model_config = {"from_attributes": True}


class DuplicateCandidateOut(BaseModel):
    candidate_project_id: str
    text_similarity: float
    geographic_similarity: float
    attribute_similarity: float
    combined_score: float
    ui_label: str  # "possible" / "strong" / "very_strong" -- never "confirmed duplicate"

    model_config = {"from_attributes": True}


class PeerBenchmarkOut(BaseModel):
    work_type: str
    group_level: str  # "district" / "state" / "state_year" / "national"
    group_value: str | None
    sample_count: int
    median_cost: float
    iqr_low: float
    iqr_high: float
    project_cost: float

    model_config = {"from_attributes": True}


class ComplianceResultOut(BaseModel):
    project_id: str
    project_code: str
    check_code: str
    result: str  # PASS / WARNING / FAIL
    evidence: dict


class RelatedProjectOut(BaseModel):
    id: str
    project_code: str
    title: str
    relationship_type: str  # "same_agency" / "same_location"


class RelationshipGraphOut(BaseModel):
    project: dict
    agency: dict | None
    location: dict | None
    payment_summary: dict
    related_projects: list[RelatedProjectOut]


class AlertItemOut(BaseModel):
    project_id: str
    project_code: str
    title: str
    final_score: float
    risk_level: str
    top_factor_code: str | None
    top_factor_explanation: str | None
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles, check_scope_access
from app.models import (
    Project, Location, RiskRun, RiskScore, RiskFactorResult, DuplicateCandidate, PeerBenchmark,
    Agency, ProjectFinancial, ProjectProgress, Payment, User, RoleName,
)
from app.schemas.risk import (
    RiskScoreOut, FactorResultOut, RiskRunOut, AlertItemOut, DuplicateCandidateOut, PeerBenchmarkOut,
    ComplianceResultOut, RelatedProjectOut, RelationshipGraphOut,
)
from app.services.risk_engine import run_risk_engine
from app.services.compliance import evaluate_compliance

router = APIRouter(tags=["risk"])


def _latest_risk_score(db: Session, project_id: str):
    return (
        db.query(RiskScore)
        .filter(RiskScore.project_id == project_id)
        .order_by(RiskScore.created_at.desc())
        .first()
    )


@router.post("/risk/recompute", response_model=RiskRunOut)
def recompute_risk(
    current_user: User = Depends(require_roles(RoleName.SYSTEM_ADMIN, RoleName.MINISTRY_ADMIN)),
    db: Session = Depends(get_db),
):
    """Scores every project. Restricted to admin roles -- recompute is a heavy, system-wide action,
    not something a district reviewer should be able to trigger for the whole country."""
    risk_run = run_risk_engine(db, triggered_by_user_id=current_user.id)
    return risk_run


@router.get("/risk/runs/{run_id}", response_model=RiskRunOut)
def get_risk_run(run_id: str, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    risk_run = db.query(RiskRun).filter(RiskRun.id == run_id).first()
    if not risk_run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Risk run not found")
    return risk_run


@router.get("/projects/{project_id}/risk", response_model=RiskScoreOut)
def get_project_risk(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    project = (
        db.query(Project).options(joinedload(Project.location))
        .filter(Project.id == project_id).first()
    )
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    if not check_scope_access(
        user,
        state=project.location.state if project.location else None,
        district=project.location.district if project.location else None,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Out of scope for this user")

    score = _latest_risk_score(db, project_id)
    if not score:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No risk score yet -- run /risk/recompute first")

    factors = (
        db.query(RiskFactorResult).filter(RiskFactorResult.risk_score_id == score.id).all()
    )
    risk_run = db.query(RiskRun).filter(RiskRun.id == score.risk_run_id).first()

    return RiskScoreOut(
        project_id=project.id,
        project_code=project.project_code,
        final_score=score.final_score,
        risk_level=score.risk_level.value,
        factors_computed_count=score.factors_computed_count,
        evidence_completeness_percent=score.evidence_completeness_percent,
        risk_run_id=score.risk_run_id,
        engine_version=risk_run.engine_version if risk_run else "unknown",
        factors=[
            FactorResultOut(
                factor_code=f.factor_code.value, raw_value=f.raw_value, normalized_score=f.normalized_score,
                weight=f.weight, contribution=f.contribution, evidence=f.evidence,
                explanation=f.explanation, detector_version=f.detector_version,
            )
            for f in factors
        ],
    )


@router.get("/projects/{project_id}/duplicates", response_model=list[DuplicateCandidateOut])
def get_project_duplicates(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Possible-duplicate candidates for this project, from the most recent risk run.
    Never labelled 'confirmed duplicate' anywhere -- ui_label is possible/strong/very_strong only."""
    project = (
        db.query(Project).options(joinedload(Project.location)).filter(Project.id == project_id).first()
    )
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if not check_scope_access(
        user, state=project.location.state if project.location else None,
        district=project.location.district if project.location else None,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Out of scope for this user")

    return (
        db.query(DuplicateCandidate)
        .filter(DuplicateCandidate.project_id == project_id)
        .order_by(DuplicateCandidate.combined_score.desc())
        .all()
    )


@router.get("/projects/{project_id}/benchmark", response_model=PeerBenchmarkOut)
def get_project_benchmark(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """The peer group (district -> state -> national fallback) actually used for this
    project's COST_DEVIATION factor in the most recent risk run, with sample size and IQR."""
    project = (
        db.query(Project).options(joinedload(Project.location)).filter(Project.id == project_id).first()
    )
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if not check_scope_access(
        user, state=project.location.state if project.location else None,
        district=project.location.district if project.location else None,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Out of scope for this user")

    latest_run = db.query(RiskRun).order_by(RiskRun.created_at.desc()).first()
    if not latest_run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No risk run yet -- run /risk/recompute first")

    district = project.location.district if project.location else None
    state = project.location.state if project.location else None

    q = db.query(PeerBenchmark).filter(
        PeerBenchmark.risk_run_id == latest_run.id, PeerBenchmark.work_type == project.work_type,
    )
    benchmark = (
        q.filter(PeerBenchmark.group_level == "district", PeerBenchmark.group_value == district).first()
        or q.filter(PeerBenchmark.group_level == "state", PeerBenchmark.group_value == state).first()
        or q.filter(PeerBenchmark.group_level == "national").first()
    )
    if not benchmark:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No peer benchmark available for this project's group")

    return PeerBenchmarkOut(
        work_type=benchmark.work_type, group_level=benchmark.group_level, group_value=benchmark.group_value,
        sample_count=benchmark.sample_count, median_cost=benchmark.median_cost,
        iqr_low=benchmark.iqr_low, iqr_high=benchmark.iqr_high, project_cost=float(project.sanctioned_amount),
    )


def _load_scoped_project(db: Session, user: User, project_id: str) -> Project:
    project = (
        db.query(Project).options(joinedload(Project.location), joinedload(Project.agency))
        .filter(Project.id == project_id).first()
    )
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if not check_scope_access(
        user, state=project.location.state if project.location else None,
        district=project.location.district if project.location else None,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Out of scope for this user")
    return project


@router.get("/projects/{project_id}/compliance", response_model=list[ComplianceResultOut])
def get_project_compliance(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Live-computed CMP-00x checks (see app/services/compliance.py) -- not read from the
    ComplianceCheck table, since nothing populates it yet. Recomputed on every call from
    current Project/Payment/Financial/Progress data, which is cheap for a single project."""
    project = _load_scoped_project(db, user, project_id)
    latest_financial = (
        db.query(ProjectFinancial).filter(ProjectFinancial.project_id == project_id)
        .order_by(ProjectFinancial.as_of_date.desc()).first()
    )
    latest_progress = (
        db.query(ProjectProgress).filter(ProjectProgress.project_id == project_id)
        .order_by(ProjectProgress.report_date.desc()).first()
    )
    payments = db.query(Payment).filter(Payment.project_id == project_id).all()

    checks = evaluate_compliance(project, latest_financial, latest_progress, payments)
    return [
        ComplianceResultOut(project_id=project.id, project_code=project.project_code, **c)
        for c in checks
    ]


@router.get("/projects/{project_id}/relationships", response_model=RelationshipGraphOut)
def get_project_relationships(
    project_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Project -> Agency -> Location -> Payments -> Related Projects, computed live from
    existing foreign keys (same agency_id / same location_id) -- NOT from the ProjectRelationship
    table, since nothing writes to it yet. No graph database, no ML -- plain SQL joins."""
    project = _load_scoped_project(db, user, project_id)

    payments = db.query(Payment).filter(Payment.project_id == project_id).all()
    payment_count = len(payments)
    payment_total_amount = float(sum(p.payment_amount for p in payments))

    related: list[RelatedProjectOut] = []
    if project.agency_id:
        same_agency = (
            db.query(Project).filter(Project.agency_id == project.agency_id, Project.id != project.id)
            .limit(10).all()
        )
        related += [
            RelatedProjectOut(id=p.id, project_code=p.project_code, title=p.title, relationship_type="same_agency")
            for p in same_agency
        ]
    if project.location_id:
        same_location = (
            db.query(Project).filter(Project.location_id == project.location_id, Project.id != project.id)
            .limit(10).all()
        )
        related += [
            RelatedProjectOut(id=p.id, project_code=p.project_code, title=p.title, relationship_type="same_location")
            for p in same_location
        ]

    return RelationshipGraphOut(
        project={"id": project.id, "project_code": project.project_code, "title": project.title},
        agency={"id": project.agency.id, "name": project.agency.name} if project.agency else None,
        location={"state": project.location.state, "district": project.location.district} if project.location else None,
        payment_summary={"count": payment_count, "total_amount": payment_total_amount},
        related_projects=related,
    )


@router.get("/alerts", response_model=list[AlertItemOut])
def get_alerts(
    min_level: str = "high",
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ranked review queue. Scoped automatically -- district/state users only see their own alerts.
    min_level: 'critical', 'high' (default, includes critical), 'medium', or 'low' (shows everything)."""
    level_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    threshold = level_order.get(min_level.lower(), 2)

    latest_run = db.query(RiskRun).order_by(RiskRun.created_at.desc()).first()
    if not latest_run:
        return []

    q = (
        db.query(RiskScore, Project, Location)
        .join(Project, RiskScore.project_id == Project.id)
        .outerjoin(Location, Project.location_id == Location.id)
        .filter(RiskScore.risk_run_id == latest_run.id)
    )

    results = []
    for score, project, location in q.all():
        score_level_rank = level_order[score.risk_level.value]
        if score_level_rank < threshold:
            continue
        if not check_scope_access(user, state=location.state if location else None,
                                    district=location.district if location else None):
            continue

        top_factor = (
            db.query(RiskFactorResult).filter(RiskFactorResult.risk_score_id == score.id)
            .order_by(RiskFactorResult.contribution.desc()).first()
        )
        results.append(AlertItemOut(
            project_id=project.id, project_code=project.project_code, title=project.title,
            final_score=score.final_score, risk_level=score.risk_level.value,
            top_factor_code=top_factor.factor_code.value if top_factor else None,
            top_factor_explanation=top_factor.explanation if top_factor else None,
        ))

    results.sort(key=lambda r: r.final_score, reverse=True)
    return results[:limit]
