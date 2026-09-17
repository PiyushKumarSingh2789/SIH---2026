"""
4-step import pipeline (canonical per PRD Section 7):
upload -> map-columns -> preview/validate -> confirm.
Named `imports.py` not `import.py` because `import` is a reserved Python keyword.
"""
import enum
import uuid
from sqlalchemy import String, ForeignKey, Enum, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ImportStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    MAPPED = "mapped"
    PREVIEWED = "previewed"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class ValidationSeverity(str, enum.Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Import(TimestampMixin, Base):
    __tablename__ = "imports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    uploaded_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus), default=ImportStatus.UPLOADED, nullable=False)
    column_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {"csv_col": "canonical_field"}
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)

    rows: Mapped[list["ImportRow"]] = relationship(back_populates="import_", cascade="all, delete-orphan")
    validation_errors: Mapped[list["ImportValidationError"]] = relationship(back_populates="import_", cascade="all, delete-orphan")


class ImportRow(TimestampMixin, Base):
    """One raw row from the uploaded file, before it becomes a Project. Kept even after confirm, for traceability."""
    __tablename__ = "import_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    import_id: Mapped[str] = mapped_column(String(36), ForeignKey("imports.id"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_valid: Mapped[bool] = mapped_column(default=True, nullable=False)
    resulting_project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("projects.id"), nullable=True)

    import_: Mapped["Import"] = relationship(back_populates="rows")


class ImportValidationError(TimestampMixin, Base):
    """One VAL-00X finding for one row. See PRD validation rules table (VAL-001..VAL-009)."""
    __tablename__ = "import_validation_errors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    import_id: Mapped[str] = mapped_column(String(36), ForeignKey("imports.id"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_code: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "VAL-003"
    severity: Mapped[ValidationSeverity] = mapped_column(Enum(ValidationSeverity), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    import_: Mapped["Import"] = relationship(back_populates="validation_errors")
