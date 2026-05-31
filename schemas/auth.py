from pydantic import BaseModel
from uuid import UUID


class RegisterRequest(BaseModel):
    username: str
    password: str
    location: str | None = None


class RegisterResponse(BaseModel):
    message: str
    user_id: UUID


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    username: str
    location: str | None = None
