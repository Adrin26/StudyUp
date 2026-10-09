from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Profile

bearer = HTTPBearer(auto_error=False)


def create_demo_token(profile_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": profile_id,
        "aud": settings.supabase_jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.token_ttl_minutes),
        "iss": "studyup-demo",
    }
    return jwt.encode(payload, settings.app_secret, algorithm="HS256")


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def decode_token(token: str) -> dict:
    settings = get_settings()
    aud = settings.supabase_jwt_audience
    if settings.auth_mode == "demo":
        return jwt.decode(token, settings.app_secret, algorithms=["HS256"], audience=aud)
    if settings.supabase_jwt_secret:
        return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience=aud)
    signing_key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token)
    return jwt.decode(token, signing_key.key, algorithms=["RS256", "ES256"], audience=aud)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Profile:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        claims = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    profile = db.get(Profile, claims.get("sub"))
    if profile is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Profile not provisioned for this account")
    return profile


def require_student(user: Profile = Depends(get_current_user)) -> Profile:
    if user.role != "student":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Students only")
    return user


def require_teacher(user: Profile = Depends(get_current_user)) -> Profile:
    if user.role not in ("teacher", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Teachers only")
    return user
