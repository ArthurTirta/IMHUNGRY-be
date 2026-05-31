import hashlib
import hmac
import os
import uuid as uuid_module
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 jam
_PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}:{key.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    salt_hex, key_hex = hashed.split(":", 1)
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(key_hex)
    candidate = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(candidate, expected)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


_bearer_scheme = HTTPBearer()
_bearer_optional = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> dict:
    """FastAPI dependency — extract JWT payload from Authorization: Bearer <token>."""
    return decode_token(credentials.credentials)


def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_optional),
) -> uuid_module.UUID | None:
    """Parse user UUID from JWT jika ada; return None untuk akses publik tanpa login."""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        return uuid_module.UUID(str(payload["sub"]))
    except HTTPException:
        return None


def get_current_user_id(current_user: dict = Depends(get_current_user)) -> uuid_module.UUID:
    """Parse user UUID from JWT `sub` claim."""
    try:
        return uuid_module.UUID(str(current_user["sub"]))
    except (ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user id in token",
        )
