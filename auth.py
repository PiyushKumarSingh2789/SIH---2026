from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ScopeOut(BaseModel):
    scope_level: str
    scope_value: str | None = None

    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    id: str
    email: str
    full_name: str
    roles: list[str]
    scopes: list[ScopeOut]
