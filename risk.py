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
