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
