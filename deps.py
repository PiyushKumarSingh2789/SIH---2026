"""
Implements: Access Allowed = Authenticated AND Required Role Present AND
                              Geographic Scope Matches AND Action Permission Present

- get_current_user: the "Authenticated" check. Every protected route depends on this.
- require_roles(...): the "Required Role Present" check, at the route level.
- check_scope_access(...): the "Geographic Scope Matches" check, at the RESOURCE level --
  call this inside a route handler once you've loaded the target project/case, comparing
  its state/district against the current user's scopes. It can't be a simple route-level
  dependency because the resource (and its state/district) isn't known until you fetch it.
- "Action Permission Present" (e.g. can this role write vs only read) is enforced by which
  routes even accept which roles in `require_roles(...)` -- there is no separate generic
  permission table in this MVP; keep it that simple unless a real need for finer grain appears.

IMPORTANT: this file is the ONLY place authorization should be decided. Do not duplicate
this logic in the frontend or re-implement scope checks ad hoc in other route files --
the PRD guardrail is explicit that the frontend can hide buttons but never grants access.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User, RoleName

# HTTPBearer gives a simple "paste your token" box in Swagger's Authorize dialog.
# (OAuth2PasswordBearer shows a username/password login form instead, which doesn't
# match our JSON-body /auth/login endpoint and was confusing to test against.)
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise credentials_error
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_roles(*allowed_roles: RoleName):
    """Route-level dependency factory. Usage: Depends(require_roles(RoleName.DISTRICT_REVIEWER))"""

    def _check(user: User = Depends(get_current_user)) -> User:
        user_role_names = {r.role_name for r in user.roles}
        if not user_role_names.intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[r.value for r in allowed_roles]}",
            )
        return user

    return _check


def check_scope_access(user: User, state: str | None = None, district: str | None = None) -> bool:
    """
    Resource-level scope check. Call this AFTER loading the target project/case, e.g.:
        project = db.query(Project).join(Location).filter(...).first()
        if not check_scope_access(user, state=project.location.state, district=project.location.district):
            raise HTTPException(403, "Out of scope")

    National-scope roles (system_administrator, ministry_administrator, auditor-with-national-scope)
    always pass. State/district scoped users must match on the relevant field.
    """
    user_role_names = {r.role_name for r in user.roles}
    if RoleName.SYSTEM_ADMIN in user_role_names or RoleName.MINISTRY_ADMIN in user_role_names:
        return True

    for scope in user.scopes:
        if scope.scope_level.value == "national":
            return True
        if scope.scope_level.value == "state" and state and scope.scope_value == state:
            return True
        if scope.scope_level.value == "district" and district and scope.scope_value == district:
            return True
    return False
