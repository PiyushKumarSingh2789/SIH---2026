"""
Risk engine tables.

CRITICAL RULE (PRD Section 4 storage requirement):
Risk scores are IMMUTABLE and VERSIONED. A recompute NEVER updates an existing risk_scores row —
it always creates a new RiskRun, then new RiskScore + RiskFactorResult rows tied to that run_id.
This is what makes /risk/recompute and the audit trail trustworthy. Do not add an "update" path here.
"""
import enum
import uuid
from datetime import date
from sqlalchemy import String, ForeignKey, Enum, Float, JSON, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class RiskLevel(str, enum.Enum):
    LOW = "low"           # 0-29
    MEDIUM = "medium"      # 30-59
    HIGH = "high"          # 60-79
    CRITICAL = "critical"  # 80-100


class FactorCode(str, enum.Enum):
    COST_DEVIATION = "COST_DEVIATION"                          # weight 0.20
    PROGRESS_EXPENDITURE_MISMATCH = "PROGRESS_EXPENDITURE_MISMATCH"  # weight 0.20
    DELAY_STALL = "DELAY_STALL"                                # weight 0.15
    PAYMENT_ANOMALY = "PAYMENT_ANOMALY"                        # weight 0.15
    DUPLICATE_SIMILARITY = "DUPLICATE_SIMILARITY"              # weight 0.10
    PEER_DEVIATION = "PEER_DEVIATION"                          # weight 0.10
    ML_ANOMALY = "ML_ANOMALY"                                  # weight 0.10, capped, Isolation Forest


# Canonical weights — import this dict wherever the scoring formula is implemented,
# never hard-code the numbers a second time.
FACTOR_WEIGHTS = {
    FactorCode.COST_DEVIATION: 0.20,
    FactorCode.PROGRESS_EXPENDITURE_MISMATCH: 0.20,
    FactorCode.DELAY_STALL: 0.15,
    FactorCode.PAYMENT_ANOMALY: 0.15,
    FactorCode.DUPLICATE_SIMILARITY: 0.10,
    FactorCode.PEER_DEVIATION: 0.10,
    FactorCode.ML_ANOMALY: 0.10,
}


class RiskRun(TimestampMixin, Base):
    """One execution of the risk engine across some/all projects. Every recompute creates a new row here."""
    __tablename__ = "risk_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)  # matches RISK_ENGINE_VERSION env
    triggered_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    project_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    scores: Mapped[list["RiskScore"]] = relationship(back_populates="risk_run", cascade="all, delete-orphan")


class RiskScore(TimestampMixin, Base):
    """One project's final score for one risk run. Never updated after creation — insert-only."""
    __tablename__ = "risk_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    risk_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_runs.id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100, Σ(w_i * s_i) / Σ(w_i)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False, index=True)
    factors_computed_count: Mapped[int] = mapped_column(Integer, nullable=False)  # |A| in the formula
    evidence_completeness_percent: Mapped[float] = mapped_column(Float, nullable=False)

    risk_run: Mapped["RiskRun"] = relationship(back_populates="scores")
    factor_results: Mapped[list["RiskFactorResult"]] = relationship(back_populates="risk_score", cascade="all, delete-orphan")


class RiskFactorResult(TimestampMixin, Base):
    """
    One factor's contribution to one risk score. This is what makes the platform explainable —
    the Project Risk Profile screen renders these as evidence cards. Every field here is mandatory,
    per PRD explainability requirement ("never show a bare AI number").
    """
    __tablename__ = "risk_factor_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    risk_score_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_scores.id"), nullable=False, index=True)
    factor_code: Mapped[FactorCode] = mapped_column(Enum(FactorCode), nullable=False)
    raw_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)  # weight * normalized_score
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)  # peer group, sample size, comparison values, etc.
    explanation: Mapped[str] = mapped_column(Text, nullable=False)  # human-readable: "what/compared to what/how much"
    detector_version: Mapped[str] = mapped_column(String(50), nullable=False)

    risk_score: Mapped["RiskScore"] = relationship(back_populates="factor_results")


class Anomaly(TimestampMixin, Base):
    """Raw detector output, independent of the weighted score — used for the Alerts/Early-Warning list views."""
    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    risk_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_runs.id"), nullable=False, index=True)
    anomaly_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g. "stall", "cost_outlier"
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)


class PeerBenchmark(TimestampMixin, Base):
    """Snapshot of a peer group's stats at the time of a risk run — stored so evidence stays auditable later."""
    __tablename__ = "peer_benchmarks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    risk_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_runs.id"), nullable=False, index=True)
    work_type: Mapped[str] = mapped_column(String(100), nullable=False)
    group_level: Mapped[str] = mapped_column(String(50), nullable=False)  # district/state/national fallback tier used
    group_value: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)  # must be >= 10 to be used
    median_cost: Mapped[float] = mapped_column(Float, nullable=False)
    iqr_low: Mapped[float] = mapped_column(Float, nullable=False)
    iqr_high: Mapped[float] = mapped_column(Float, nullable=False)


class DuplicateCandidate(TimestampMixin, Base):
    """Never call this 'confirmed duplicate' anywhere in the UI — it's always a candidate for human review."""
    __tablename__ = "duplicate_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    candidate_project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    text_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    geographic_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    attribute_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    combined_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.60*text + 0.25*geo + 0.15*attr
    ui_label: Mapped[str] = mapped_column(String(50), nullable=False)  # "possible" / "strong" / "very strong"


class ProjectRelationship(TimestampMixin, Base):
    """Edges for the relationship/evidence graph: Project -> Agency/Location/Payment/Related-Project (P1 feature)."""
    __tablename__ = "project_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    from_project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    to_project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)  # "same_agency", "same_location", etc.
    strength: Mapped[float | None] = mapped_column(Float, nullable=True)


class ComplianceCheck(TimestampMixin, Base):
    """CMP-001..CMP-007 results per project per run. PASS/WARNING/FAIL (P1 feature)."""
    __tablename__ = "compliance_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    risk_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_runs.id"), nullable=False, index=True)
    check_code: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "CMP-002"
    result: Mapped[str] = mapped_column(String(20), nullable=False)  # PASS / WARNING / FAIL
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
