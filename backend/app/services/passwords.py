"""Password hashing, policy and single-use reset tokens (AUTH_MODE=local).

Hashes use scrypt from the standard library: `scrypt$n$r$p$salt$hash`.
Raw reset tokens are only ever returned to the caller to be emailed; the
database stores their SHA-256.
"""

import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import LocalCredential, PasswordResetToken, Profile, utcnow

_N, _R, _P = 2**14, 8, 1
MIN_LENGTH, MAX_LENGTH = 8, 128


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, digest = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verifying against this when the account does not exist keeps response time
# similar for real and unknown identifiers.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def verify_or_burn(password: str, cred: LocalCredential | None) -> bool:
    if cred is None:
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, cred.password_hash)


def password_problems(password: str, identifiers: tuple[str | None, ...] = ()) -> list[str]:
    problems = []
    if len(password) < MIN_LENGTH:
        problems.append(f"Use at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        problems.append(f"Use at most {MAX_LENGTH} characters.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        problems.append("Include at least one letter and one number.")
    lowered = password.lower()
    if any(i and lowered == i.lower() for i in identifiers):
        problems.append("Do not use your email or username as your password.")
    return problems


def set_password(db: Session, profile: Profile, password: str) -> None:
    cred = db.get(LocalCredential, profile.id)
    if cred is None:
        cred = LocalCredential(profile_id=profile.id, password_hash=hash_password(password))
        db.add(cred)
    else:
        cred.password_hash = hash_password(password)
    cred.password_changed_at = utcnow()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_reset_token(db: Session, profile: Profile, requested_by: str | None = None) -> str:
    now = utcnow()
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.profile_id == profile.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        profile_id=profile.id,
        token_hash=_digest(token),
        expires_at=now + timedelta(minutes=get_settings().password_reset_ttl_minutes),
        requested_by=requested_by,
    ))
    return token


def consume_reset_token(db: Session, token: str) -> Profile | None:
    row = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == _digest(token)))
    if row is None or row.used_at is not None or row.expires_at <= utcnow():
        return None
    profile = db.get(Profile, row.profile_id)
    if profile is None or not profile.is_active:
        return None
    row.used_at = utcnow()
    return profile
