"""
RBAC foundation: users, roles, user_scopes.
Every protected API route checks: Authenticated AND Role Present AND Scope Matches AND Permission Present.
This check happens ONLY in the backend (see PRD Section 3) — never trust the frontend for authorization.
"""
import enum
import uuid
from sqlalchemy import String, ForeignKey, Enum, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class RoleName(str, enum.Enum):
    SYSTEM_ADMIN = "system_administrator"
    MINISTRY_ADMIN = "ministry_administrator"
    STATE_OFFICER = "state_officer"
    DISTRICT_REVIEWER = "district_reviewer"
    FIELD_VERIFIER = "field_verifier"
    AUDITOR = "auditor"
    CITIZEN = "citizen"


class ScopeLevel(str, enum.Enum):
    NATIONAL = "national"
    STATE = "state"
    DISTRICT = "district"
    WORK = "work"          # field verifier scoped to a specific work/project
    CUSTOM = "custom"       # auditor with an approved ad-hoc scope


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)  # Argon2/bcrypt hash only
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    roles: Mapped[list["Role"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    scopes: Mapped[list["UserScope"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Role(TimestampMixin, Base):
    """A user can hold more than one role (e.g. a district reviewer who is also a field verifier)."""
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    role_name: Mapped[RoleName] = mapped_column(Enum(RoleName), nullable=False)

    user: Mapped["User"] = relationship(back_populates="roles")


class UserScope(TimestampMixin, Base):
    """
    Geographic/organizational boundary for a user's role.
    e.g. role_name=DISTRICT_REVIEWER + scope_level=DISTRICT + scope_value="Lucknow"
    National-scope roles (ministry_admin, system_admin) get scope_level=NATIONAL, scope_value=NULL.
    """
    __tablename__ = "user_scopes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    scope_level: Mapped[ScopeLevel] = mapped_column(Enum(ScopeLevel), nullable=False)
    scope_value: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # e.g. state or district name

    user: Mapped["User"] = relationship(back_populates="scopes")
