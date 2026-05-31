from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str
    location: str | None = None


class RegisterResponse(BaseModel):
    message: str
    user_id: int


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    location: str | None = None
