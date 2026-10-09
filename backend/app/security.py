"""Identity: issuing and verifying access tokens and resolving the current profile.

Role and scope checks live in `permissions.py` and `services/access.py`.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import LocalCredential, Profile

bearer = HTTPBearer(auto_error=False)
LOCAL_ISSUER = "minda-local"


def auth_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, {"code": code, "message": message})


def account_disabled() -> HTTPException:
    return auth_error(
        status.HTTP_403_FORBIDDEN,
        "account_disabled",
        "This account has been disabled. Please contact your school administrator.",
    )


def password_version(cred: LocalCredential) -> int:
    return int(cred.password_changed_at.timestamp() * 1000)


def create_access_token(profile_id: str, cred: LocalCredential) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    ttl = settings.token_ttl_minutes * 60
    payload = {
        "sub": profile_id,
        "aud": settings.supabase_jwt_audience,
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
        "iss": LOCAL_ISSUER,
        "pwv": password_version(cred),
    }
    return jwt.encode(payload, settings.app_secret, algorithm="HS256"), ttl


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def decode_token(token: str) -> dict:
    settings = get_settings()
    aud = settings.supabase_jwt_audience
    if settings.auth_mode == "local":
        return jwt.decode(token, settings.app_secret, algorithms=["HS256"], audience=aud, issuer=LOCAL_ISSUER)
    if settings.supabase_jwt_secret:
        return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience=aud)
    signing_key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token)
    return jwt.decode(token, signing_key.key, algorithms=["RS256", "ES256"], audience=aud)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Profile:
    if credentials is None:
        raise auth_error(status.HTTP_401_UNAUTHORIZED, "not_authenticated", "Please sign in to continue.")
    try:
        claims = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise auth_error(status.HTTP_401_UNAUTHORIZED, "session_expired", "Your session has expired. Please sign in again.") from exc
    profile = db.get(Profile, claims.get("sub"))
    if profile is None:
        raise auth_error(status.HTTP_403_FORBIDDEN, "not_provisioned", "Your account has not been set up yet. Please contact your school administrator.")
    if not profile.is_active:
        raise account_disabled()
    if get_settings().auth_mode == "local":
        cred = db.get(LocalCredential, profile.id)
        if cred is None or claims.get("pwv") != password_version(cred):
            raise auth_error(status.HTTP_401_UNAUTHORIZED, "session_expired", "Your password was changed. Please sign in again.")
    return profile
