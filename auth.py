from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, MeResponse, ScopeOut
from app.services.auth_service import authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        # Deliberately generic message -- never reveal whether the email exists.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    role_names = [r.role_name.value for r in user.roles]
    access_token = create_access_token(subject=user.id, extra_claims={"roles": role_names})
    refresh_token = create_refresh_token(subject=user.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token)
        if decoded.get("type") != "refresh":
            raise JWTError("wrong token type")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == decoded["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer active")

    role_names = [r.role_name.value for r in user.roles]
    new_access = create_access_token(subject=user.id, extra_claims={"roles": role_names})
    new_refresh = create_refresh_token(subject=user.id)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.get("/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        roles=[r.role_name.value for r in current_user.roles],
        scopes=[ScopeOut(scope_level=s.scope_level.value, scope_value=s.scope_value) for s in current_user.scopes],
    )
