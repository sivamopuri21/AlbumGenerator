"""
Authentication routes - simple token-based auth.
"""
import hashlib
import time
import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

# Simple token store (in production, use Redis or DB)
_active_tokens: dict[str, float] = {}  # token -> expiry timestamp
TOKEN_EXPIRY = 24 * 60 * 60  # 24 hours

security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    expires_in: int


def _generate_token(username: str) -> str:
    raw = f"{username}:{time.time()}:{settings.auth_secret_key}"
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    if req.username != settings.auth_username or req.password != settings.auth_password:
        logger.warning("Failed login attempt: %s", req.username)
        raise HTTPException(401, "Invalid username or password")

    token = _generate_token(req.username)
    _active_tokens[token] = time.time() + TOKEN_EXPIRY
    logger.info("User '%s' logged in", req.username)
    return LoginResponse(token=token, expires_in=TOKEN_EXPIRY)


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials and credentials.credentials in _active_tokens:
        del _active_tokens[credentials.credentials]
    return {"message": "Logged out"}


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Dependency to verify auth token on protected routes."""
    if not credentials:
        raise HTTPException(401, "Authentication required")
    token = credentials.credentials
    if token not in _active_tokens:
        raise HTTPException(401, "Invalid or expired token")
    if time.time() > _active_tokens[token]:
        del _active_tokens[token]
        raise HTTPException(401, "Token expired")
    return token
