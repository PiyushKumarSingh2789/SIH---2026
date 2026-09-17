from datetime import datetime
from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    created_at: datetime
    user_id: str | None
    user_name: str | None  # resolved from users table at read time; None if the user was deleted
    role_at_time: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    description: str  # synthesized at read time from remark/action/previous_value/new_value -- not stored
"""
GET /audit -- a global, system-wide audit trail. Reads the EXISTING audit_logs table (see
app/models/misc.py::AuditLog) which case_service.py already writes to on every case creation
and status change. This file adds no new table and writes nothing -- it's read-only.

Access: system_administrator, ministry_administrator, and auditor only. This matches the PRD's
role table, where "auditor" is explicitly the role scoped to "Read evidence and audit history" --
a district reviewer or state officer can already see the audit trail for their OWN cases via
GET /cases/{id} (status_history), but a cross-entity, system-wide log is a different, broader
capability that only the oversight-level roles get here.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models import AuditLog, User, RoleName
from app.schemas.audit import AuditLogOut

router = APIRouter(prefix="/audit", tags=["audit"])

_audit_roles = require_roles(RoleName.SYSTEM_ADMIN, RoleName.MINISTRY_ADMIN, RoleName.AUDITOR)


def _describe(log: AuditLog) -> str:
    """Human-readable line built ONLY from data already on the row -- never invented.
    Prefers the actual remark (present for every case status change); falls back to
    reading previous/new_value when present; otherwise humanizes the action code itself."""
    if log.remark:
        return log.remark
    if log.action == "case.created" and log.new_value:
        return f"Created with status '{log.new_value.get('status')}'."
    if log.action == "case.status_changed" and log.previous_value and log.new_value:
        return f"Status changed from '{log.previous_value.get('status')}' to '{log.new_value.get('status')}'."
    return log.action.replace(".", " ").replace("_", " ").capitalize() + "."


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    user_id: str | None = None,
    role: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    _current_user: User = Depends(_audit_roles),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)

    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if role:
        q = q.filter(AuditLog.role_at_time.ilike(f"%{role}%"))
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLog.entity_id == entity_id)
    if date_from:
        q = q.filter(AuditLog.created_at >= date_from)
    if date_to:
        q = q.filter(AuditLog.created_at <= date_to)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (AuditLog.action.ilike(like)) | (AuditLog.entity_type.ilike(like))
            | (AuditLog.entity_id.ilike(like)) | (AuditLog.remark.ilike(like))
        )

    logs = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    user_ids = {log.user_id for log in logs if log.user_id}
    users_by_id = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            users_by_id[u.id] = u.full_name

    return [
        AuditLogOut(
            id=log.id, created_at=log.created_at, user_id=log.user_id,
            user_name=users_by_id.get(log.user_id), role_at_time=log.role_at_time,
            action=log.action, entity_type=log.entity_type, entity_id=log.entity_id,
            description=_describe(log),
        )
        for log in logs
    ]
