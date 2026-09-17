"""
citizen_reports: public-facing discrepancy submissions (additional evidence, never automatic proof).
audit_logs: append-only log of every sensitive action across the whole system, not just cases.
"""
import uuid
from sqlalchemy import String, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class CitizenReport(TimestampMixin, Base):
    __tablename__ = "citizen_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    reference_id: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)  # shown to citizen
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # not_completed/quality/not_found/duplicate/other
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reporter_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)  # optional, public user may stay anonymous
    status: Mapped[str] = mapped_column(String(50), default="received", nullable=False)


class AuditLog(TimestampMixin, Base):
    """
    Append-only. NEVER update or delete rows here — if you need to "undo" something, write a new
    audit row describing the correction. This table is what you show a judge who asks "how do you
    know officers didn't just quietly change a decision?"
    """
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    role_at_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(150), nullable=False, index=True)  # e.g. "case.status_changed"
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "case", "project", "import"
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    previous_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
