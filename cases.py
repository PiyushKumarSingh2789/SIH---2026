from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user, check_scope_access
from app.models import Case, CaseComment, CaseEvidence, CaseStatusHistory, CaseAssignment, CaseStatus, Project, User
from app.schemas.cases import (
    CaseCreateRequest, CaseOut, CaseDetailOut, StatusChangeRequest, StatusHistoryOut,
    CommentRequest, CommentOut, EvidenceRequest, EvidenceOut, CaseBriefOut, AssignmentOut,
)
from app.services.case_service import create_case, change_case_status, generate_case_brief, InvalidTransitionError

router = APIRouter(prefix="/cases", tags=["cases"])


def _load_case_or_404(db: Session, case_id: str) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case


def _check_case_scope(db: Session, case: Case, user: User) -> None:
    project = (
        db.query(Project).options(joinedload(Project.location)).filter(Project.id == case.project_id).first()
    )
    state = project.location.state if project and project.location else None
    district = project.location.district if project and project.location else None
    if not check_scope_access(user, state=state, district=district):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Out of scope for this user")


@router.post("", response_model=CaseOut)
def create_case_route(
    payload: CaseCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    project = db.query(Project).options(joinedload(Project.location)).filter(Project.id == payload.project_id).first()
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if not check_scope_access(user, state=project.location.state if project.location else None,
                                district=project.location.district if project.location else None):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Out of scope for this user")

    case = create_case(db, payload.project_id, payload.risk_score_id, user)
    return CaseOut(id=case.id, project_id=case.project_id, project_code=project.project_code,
                    status=case.status.value, created_by_user_id=case.created_by_user_id, created_at=case.created_at)


@router.get("", response_model=list[CaseOut])
def list_cases(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cases = db.query(Case).options(joinedload(Case.project).joinedload(Project.location)).all()

    results = []
    for case in cases:
        project = case.project
        state = project.location.state if project and project.location else None
        district = project.location.district if project and project.location else None
        if not check_scope_access(user, state=state, district=district):
            continue
        results.append(CaseOut(
            id=case.id, project_id=case.project_id, project_code=project.project_code if project else "?",
            status=case.status.value, created_by_user_id=case.created_by_user_id, created_at=case.created_at,
        ))
    return results


@router.get("/{case_id}", response_model=CaseDetailOut)
def get_case(case_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = _load_case_or_404(db, case_id)
    _check_case_scope(db, case, user)
    project = (
        db.query(Project).options(joinedload(Project.location)).filter(Project.id == case.project_id).first()
    )

    comments = db.query(CaseComment).filter(CaseComment.case_id == case_id).order_by(CaseComment.created_at).all()
    evidence = db.query(CaseEvidence).filter(CaseEvidence.case_id == case_id).order_by(CaseEvidence.created_at).all()
    history = (
        db.query(CaseStatusHistory).filter(CaseStatusHistory.case_id == case_id)
        .order_by(CaseStatusHistory.created_at).all()
    )
    assignments = (
        db.query(CaseAssignment).filter(CaseAssignment.case_id == case_id)
        .order_by(CaseAssignment.created_at).all()
    )

    return CaseDetailOut(
        id=case.id, project_id=case.project_id, project_code=project.project_code if project else "?",
        status=case.status.value, created_by_user_id=case.created_by_user_id, created_at=case.created_at,
        comments=[CommentOut.model_validate(c) for c in comments],
        evidence=[EvidenceOut.model_validate(e) for e in evidence],
        status_history=[
            StatusHistoryOut(from_status=h.from_status.value if h.from_status else None,
                              to_status=h.to_status.value, changed_by_user_id=h.changed_by_user_id,
                              remark=h.remark, created_at=h.created_at)
            for h in history
        ],
        assignments=[AssignmentOut.model_validate(a) for a in assignments],
        state=project.location.state if project and project.location else None,
        district=project.location.district if project and project.location else None,
    )


@router.patch("/{case_id}/status", response_model=CaseOut)
def update_case_status(
    case_id: str, payload: StatusChangeRequest,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    case = _load_case_or_404(db, case_id)
    _check_case_scope(db, case, user)

    try:
        new_status_enum = CaseStatus(payload.new_status)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown status '{payload.new_status}'")

    try:
        case = change_case_status(db, case, new_status_enum, payload.remark, user)
    except InvalidTransitionError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))

    project = db.query(Project).filter(Project.id == case.project_id).first()
    return CaseOut(id=case.id, project_id=case.project_id, project_code=project.project_code if project else "?",
                    status=case.status.value, created_by_user_id=case.created_by_user_id, created_at=case.created_at)


@router.post("/{case_id}/comments", response_model=CommentOut)
def add_comment(
    case_id: str, payload: CommentRequest,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    case = _load_case_or_404(db, case_id)
    _check_case_scope(db, case, user)

    comment = CaseComment(case_id=case_id, author_user_id=user.id, body=payload.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.post("/{case_id}/evidence", response_model=EvidenceOut)
def add_evidence(
    case_id: str, payload: EvidenceRequest,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    case = _load_case_or_404(db, case_id)
    _check_case_scope(db, case, user)

    evidence = CaseEvidence(
        case_id=case_id, evidence_category=payload.evidence_category,
        description=payload.description, file_reference=payload.file_reference,
        uploaded_by_user_id=user.id,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


@router.get("/{case_id}/brief", response_model=CaseBriefOut)
def get_case_brief(case_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = _load_case_or_404(db, case_id)
    _check_case_scope(db, case, user)
    brief = generate_case_brief(db, case)
    return CaseBriefOut(**brief)


@router.get("/{case_id}/audit", response_model=list[StatusHistoryOut])
def get_case_audit(case_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    case = _load_case_or_404(db, case_id)
    _check_case_scope(db, case, user)
    history = (
        db.query(CaseStatusHistory).filter(CaseStatusHistory.case_id == case_id)
        .order_by(CaseStatusHistory.created_at).all()
    )
    return [
        StatusHistoryOut(from_status=h.from_status.value if h.from_status else None,
                          to_status=h.to_status.value, changed_by_user_id=h.changed_by_user_id,
                          remark=h.remark, created_at=h.created_at)
        for h in history
    ]
