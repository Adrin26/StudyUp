"""Admin-managed accounts: uniqueness checks, creation and set-password links.

New accounts never get a password chosen by the admin. They receive a
single-use link (the same token mechanism as password reset) to choose their
own, so no one but the user ever knows it.
"""

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Profile, School
from . import audit, mailer, passwords

FIELD_LABELS = {"email": "Email", "username": "Username", "student_number": "Student ID", "staff_number": "Staff ID"}


def conflicts(
    db: Session,
    school_id: str | None,
    values: dict[str, str | None],
    exclude_id: str | None = None,
) -> dict[str, str]:
    """Which unique identity fields are already taken. Email/username are global; ID numbers are per school."""
    out: dict[str, str] = {}
    for field, value in values.items():
        if not value or field not in FIELD_LABELS:
            continue
        column = getattr(Profile, field)
        stmt = select(Profile.id).where(func.lower(column) == value.lower())
        if field in ("student_number", "staff_number"):
            stmt = stmt.where(Profile.school_id == school_id)
        if exclude_id:
            stmt = stmt.where(Profile.id != exclude_id)
        if db.scalar(stmt.limit(1)):
            out[field] = f"{FIELD_LABELS[field]} {value} is already in use"
    return out


def raise_conflicts(found: dict[str, str]) -> None:
    if found:
        raise HTTPException(status.HTTP_409_CONFLICT, "; ".join(found.values()))


def suggest_username(db: Session, email: str, reserved: set[str] = frozenset()) -> str:
    base = "".join(c for c in email.split("@")[0].lower() if c.isalnum() or c in "._-")[:50] or "user"
    if len(base) < 3:
        base = f"{base}user"
    candidate, n = base, 1
    while candidate in reserved or db.scalar(select(Profile.id).where(func.lower(Profile.username) == candidate)):
        n += 1
        candidate = f"{base}{n}"
    return candidate


def require_local_accounts() -> None:
    if get_settings().auth_mode != "local":
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Creating accounts and sending set-password links through Supabase Auth is not available yet. "
            "Invite the user from the Supabase dashboard; their profile is created automatically.",
        )


def send_set_password_link(db: Session, user: Profile, actor: Profile, request: Request | None, *, invitation: bool) -> bool:
    """Issue a single-use link and email it. Returns whether the email was handed to a mail provider."""
    s = get_settings()
    token = passwords.issue_reset_token(db, user, requested_by=actor.id, ttl_minutes=s.invite_ttl_hours * 60)
    link = f"{s.frontend_url.rstrip('/')}/reset-password?token={token}"
    if invitation:
        school = db.get(School, user.school_id) if user.school_id else None
        delivered = mailer.send_invitation(user.email, user.full_name, school.name if school else None, link, s.invite_ttl_hours)
    else:
        delivered = mailer.send_password_reset(user.email, user.full_name, link, s.invite_ttl_hours * 60)
    action = "user.invitation_sent" if invitation else "auth.password_reset_requested"
    audit.record(db, action, "profile", user.id, actor=actor, request=request, details={"via": "admin", "delivered": delivered})
    return delivered


def delivery_message(delivered: bool) -> str:
    if delivered and get_settings().is_development:
        return "Link created. Email is not configured in development, so the link was printed to the API console."
    if delivered:
        return "A set-password link was emailed to the user."
    return "The link was created but could not be emailed because no email provider is configured."
