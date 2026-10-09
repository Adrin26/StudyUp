"""Audit trail for significant administrative and account actions."""

from fastapi import Request
from sqlalchemy.orm import Session

from ..models import AuditLog, Profile

_FORBIDDEN_KEYS = {"password", "new_password", "current_password", "token", "access_token", "password_hash", "secret"}


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def record(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    *,
    actor: Profile | None = None,
    school_id: str | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Add an audit entry to the session; the caller commits with its own change."""
    safe = {k: v for k, v in (details or {}).items() if k.lower() not in _FORBIDDEN_KEYS}
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        school_id=school_id if school_id is not None else (actor.school_id if actor else None),
        details=safe,
        ip_address=client_ip(request),
    )
    db.add(entry)
    return entry
