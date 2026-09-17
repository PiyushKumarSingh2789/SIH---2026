from datetime import datetime
from pydantic import BaseModel


class CaseCreateRequest(BaseModel):
    project_id: str
    risk_score_id: str | None = None


class CaseOut(BaseModel):
    id: str
    project_id: str
    project_code: str
    status: str
    created_by_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StatusChangeRequest(BaseModel):
    new_status: str
    remark: str  # mandatory -- see case.py model comment on case_status_history.remark


class StatusHistoryOut(BaseModel):
    from_status: str | None
    to_status: str
    changed_by_user_id: str
    remark: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentRequest(BaseModel):
    body: str


class CommentOut(BaseModel):
    author_user_id: str
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EvidenceRequest(BaseModel):
    evidence_category: str  # financial / execution / field / ai / public
    description: str
    file_reference: str | None = None


class EvidenceOut(BaseModel):
    evidence_category: str
    description: str
    file_reference: str | None
    uploaded_by_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AssignmentOut(BaseModel):
    assigned_to_user_id: str
    assigned_by_user_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseDetailOut(BaseModel):
    id: str
    project_id: str
    project_code: str
    status: str
    created_by_user_id: str
    created_at: datetime
    comments: list[CommentOut]
    evidence: list[EvidenceOut]
    status_history: list[StatusHistoryOut]
    assignments: list[AssignmentOut] = []
    state: str | None = None
    district: str | None = None


class CaseBriefOut(BaseModel):
    """Fixed-template investigation brief per PRD Section 20 -- must work without any LLM call."""
    project_code: str
    project_title: str
    risk_score: float | None
    risk_level: str | None
    top_factors: list[str]
    case_status: str
    recommended_verification_priority: str
    disclaimer: str = (
        "This brief summarizes stored evidence for human review. It does not constitute a finding "
        "of fraud, guilt, or corruption. Final decisions rest with authorized officers."
    )
