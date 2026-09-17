"""
Core MPLADS project domain.
IMPORTANT: sanctioned_amount / utilized_amount / payment_amount / estimated_cost all use
DECIMAL(15,2) per PRD storage rule — never Float, to avoid binary floating point drift on money.
"""
import enum
import uuid
from datetime import date
from sqlalchemy import String, ForeignKey, Enum, DECIMAL, Date, Float, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ProjectStatus(str, enum.Enum):
    RECOMMENDED = "recommended"
    SANCTIONED = "sanctioned"
    IN_PROGRESS = "in_progress"
    STALLED = "stalled"
    COMPLETED = "completed"
    CLOSED = "closed"


class Agency(TimestampMixin, Base):
    __tablename__ = "agencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agency_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    projects: Mapped[list["Project"]] = relationship(back_populates="agency")


class Location(TimestampMixin, Base):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    state: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    constituency: Mapped[str | None] = mapped_column(String(150), nullable=True)
    village_ward: Mapped[str | None] = mapped_column(String(150), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    projects: Mapped[list["Project"]] = relationship(back_populates="location")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)  # VAL-001
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), nullable=False, index=True)

    agency_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agencies.id"), nullable=True, index=True)
    location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("locations.id"), nullable=True, index=True)

    recommendation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sanction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expected_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    sanctioned_amount: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=False)   # VAL-002: >= 0
    estimated_cost: Mapped[float | None] = mapped_column(DECIMAL(15, 2), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(50), nullable=True)
    asset_status: Mapped[str | None] = mapped_column(String(100), nullable=True)

    agency: Mapped["Agency"] = relationship(back_populates="projects")
    location: Mapped["Location"] = relationship(back_populates="projects")
    financials: Mapped[list["ProjectFinancial"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    progress_reports: Mapped[list["ProjectProgress"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    assets: Mapped[list["ProjectAsset"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_projects_state_district_worktype", "work_type"),  # composite added via location join in queries
    )


class ProjectFinancial(TimestampMixin, Base):
    """Running utilization snapshot — separate from raw payments so utilization_ratio can be queried cheaply."""
    __tablename__ = "project_financials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    utilized_amount: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=False, default=0)  # VAL-006 vs sanctioned
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="financials")


class ProjectProgress(TimestampMixin, Base):
    __tablename__ = "project_progress"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    physical_progress_percent: Mapped[float] = mapped_column(Float, nullable=False)  # VAL-003: 0-100
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="progress_reports")


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    payment_amount: Mapped[float] = mapped_column(DECIMAL(15, 2), nullable=False)
    payment_reference: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="payments")


class ProjectAsset(TimestampMixin, Base):
    __tablename__ = "project_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    asset_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="assets")
