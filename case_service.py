"""
Case workflow service. The state machine itself (VALID_TRANSITIONS) lives in app/models/case.py --
this file enforces it and writes the audit trail. Never allow a status change to bypass this function.
"""
from sqlalchemy.orm import Session

from app.models import (
    Case, CaseStatus, CaseStatusHistory, AuditLog, VALID_TRANSITIONS,
    Project, RiskScore, RiskFactorResult, User,
)


class InvalidTransitionError(Exception):
    pass


def create_case(db: Session, project_id: str, risk_score_id: str | None, user: User) -> Case:
    case = Case(
        project_id=project_id, risk_score_id=risk_score_id,
        status=CaseStatus.AI_FLAGGED, created_by_user_id=user.id,
    )
    db.add(case)
    db.flush()

    db.add(CaseStatusHistory(
        case_id=case.id, from_status=None, to_status=CaseStatus.AI_FLAGGED,
        changed_by_user_id=user.id, remark="Case created.",
    ))
    db.add(AuditLog(
        user_id=user.id, role_at_time=",".join(r.role_name.value for r in user.roles),
        action="case.created", entity_type="case", entity_id=case.id,
        new_value={"status": CaseStatus.AI_FLAGGED.value, "project_id": project_id},
    ))
    db.commit()
    db.refresh(case)
    return case


def change_case_status(db: Session, case: Case, new_status: CaseStatus, remark: str, user: User) -> Case:
    if not remark or not remark.strip():
        raise ValueError("A remark is required for every status transition.")

    allowed = VALID_TRANSITIONS.get(case.status, [])
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot move from '{case.status.value}' to '{new_status.value}'. "
            f"Valid next states: {[s.value for s in allowed]}"
        )

    old_status = case.status
    case.status = new_status
    db.add(CaseStatusHistory(
        case_id=case.id, from_status=old_status, to_status=new_status,
        changed_by_user_id=user.id, remark=remark,
    ))
    db.add(AuditLog(
        user_id=user.id, role_at_time=",".join(r.role_name.value for r in user.roles),
        action="case.status_changed", entity_type="case", entity_id=case.id,
        previous_value={"status": old_status.value}, new_value={"status": new_status.value}, remark=remark,
    ))
    db.commit()
    db.refresh(case)
    return case


def generate_case_brief(db: Session, case: Case) -> dict:
    """Fixed-template brief per PRD Section 20 -- populated entirely from stored data, no LLM call.
    This must always work even if an optional LLM assistant (P1, not built yet) is unavailable."""
    project = db.query(Project).filter(Project.id == case.project_id).first()

    risk_score = None
    top_factors: list[str] = []
    if case.risk_score_id:
        risk_score = db.query(RiskScore).filter(RiskScore.id == case.risk_score_id).first()
    elif project:
        risk_score = (
            db.query(RiskScore).filter(RiskScore.project_id == project.id)
            .order_by(RiskScore.created_at.desc()).first()
        )
    if risk_score:
        factors = (
            db.query(RiskFactorResult).filter(RiskFactorResult.risk_score_id == risk_score.id)
            .order_by(RiskFactorResult.contribution.desc()).limit(3).all()
        )
        top_factors = [f.explanation for f in factors]

    priority = "Standard"
    if risk_score:
        if risk_score.risk_level.value == "critical":
            priority = "Immediate"
        elif risk_score.risk_level.value == "high":
            priority = "High"

    return {
        "project_code": project.project_code if project else "UNKNOWN",
        "project_title": project.title if project else "UNKNOWN",
        "risk_score": risk_score.final_score if risk_score else None,
        "risk_level": risk_score.risk_level.value if risk_score else None,
        "top_factors": top_factors,
        "case_status": case.status.value,
        "recommended_verification_priority": priority,
    }
