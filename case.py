"""
Case workflow — implements the state machine from PRD Section 3:

AI_FLAGGED -> UNDER_REVIEW -> FIELD_VERIFICATION_REQUESTED -> FIELD_VERIFICATION_COMPLETED -> DECISION_PENDING
DECISION_PENDING -> NO_ISSUE_CLOSED
DECISION_PENDING -> IRREGULARITY_ESCALATED -> ACTION_TAKEN -> CLOSED
DECISION_PENDING -> INCONCLUSIVE_REVERIFY -> FIELD_VERIFICATION_REQUESTED

RULE: every status transition MUST create a CaseStatusHistory row with a remark. Enforce this in the
service layer (PATCH /cases/{id}/status), never allow a direct status column update anywhere else.
"""
import enum
import uuid
from sqlalchemy import String, ForeignKey, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class CaseStatus(str, enum.Enum):
    AI_FLAGGED = "ai_flagged"
    UNDER_REVIEW = "under_review"
    FIELD_VERIFICATION_REQUESTED = "field_verification_requested"
    FIELD_VERIFICATION_COMPLETED = "field_verification_completed"
    DECISION_PENDING = "decision_pending"
    NO_ISSUE_CLOSED = "no_issue_closed"
    IRREGULARITY_ESCALATED = "irregularity_escalated"
    ACTION_TAKEN = "action_taken"
    INCONCLUSIVE_REVERIFY = "inconclusive_reverify"
    CLOSED = "closed"


# Valid transitions — the service layer must reject any PATCH that isn't in this map.
VALID_TRANSITIONS: dict[CaseStatus, list[CaseStatus]] = {
    CaseStatus.AI_FLAGGED: [CaseStatus.UNDER_REVIEW],
    CaseStatus.UNDER_REVIEW: [CaseStatus.FIELD_VERIFICATION_REQUESTED],
    CaseStatus.FIELD_VERIFICATION_REQUESTED: [CaseStatus.FIELD_VERIFICATION_COMPLETED],
    CaseStatus.FIELD_VERIFICATION_COMPLETED: [CaseStatus.DECISION_PENDING],
    CaseStatus.DECISION_PENDING: [
        CaseStatus.NO_ISSUE_CLOSED,
        CaseStatus.IRREGULARITY_ESCALATED,
        CaseStatus.INCONCLUSIVE_REVERIFY,
    ],
    CaseStatus.IRREGULARITY_ESCALATED: [CaseStatus.ACTION_TAKEN],
    CaseStatus.ACTION_TAKEN: [CaseStatus.CLOSED],
    CaseStatus.INCONCLUSIVE_REVERIFY: [CaseStatus.FIELD_VERIFICATION_REQUESTED],
    CaseStatus.NO_ISSUE_CLOSED: [],
    CaseStatus.CLOSED: [],
}


class Case(TimestampMixin, Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    risk_score_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("risk_scores.id"), nullable=True)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.AI_FLAGGED, nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    assignments: Mapped[list["CaseAssignment"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    evidence: Mapped[list["CaseEvidence"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    comments: Mapped[list["CaseComment"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    status_history: Mapped[list["CaseStatusHistory"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    project: Mapped["Project"] = relationship()  # read-only convenience relationship, no back_populates needed


class CaseAssignment(TimestampMixin, Base):
    __tablename__ = "case_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    assigned_to_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    assigned_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    case: Mapped["Case"] = relationship(back_populates="assignments")


class CaseEvidence(TimestampMixin, Base):
    """Financial / execution / field / AI / public evidence categories per PRD Section 13."""
    __tablename__ = "case_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    evidence_category: Mapped[str] = mapped_column(String(50), nullable=False)  # financial/execution/field/ai/public
    description: Mapped[str] = mapped_column(Text, nullable=False)
    file_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)  # storage path/URL, never the raw file in DB
    uploaded_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    case: Mapped["Case"] = relationship(back_populates="evidence")


class CaseComment(TimestampMixin, Base):
    __tablename__ = "case_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    author_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    case: Mapped["Case"] = relationship(back_populates="comments")


class CaseStatusHistory(TimestampMixin, Base):
    """Immutable log of every transition. This + audit_logs is what makes the case workflow trustworthy."""
    __tablename__ = "case_status_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id"), nullable=False, index=True)
    from_status: Mapped[CaseStatus | None] = mapped_column(Enum(CaseStatus), nullable=True)
    to_status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), nullable=False)
    changed_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    remark: Mapped[str] = mapped_column(Text, nullable=False)  # mandatory — never allow an empty remark

    case: Mapped["Case"] = relationship(back_populates="status_history")
