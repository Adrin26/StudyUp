from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import ClassStudent, LocalCredential, Profile, School, SchoolClass, utcnow
from ..schemas import ChangePasswordIn, ForgotPasswordIn, LoginIn, ResetPasswordIn
from ..security import account_disabled, create_access_token, get_current_user
from ..services import audit, mailer, passwords
from ..services.access import teacher_responsibilities
from ..services.rate_limit import limiter, too_many

router = APIRouter(prefix="/api/auth", tags=["auth"])

BAD_CREDENTIALS = "Incorrect email/username or password"
RECOVERY_MESSAGE = "If an active account matches, a password reset link has been sent."


def profile_payload(db: Session, user: Profile) -> dict:
    school = db.get(School, user.school_id) if user.school_id else None
    class_name = None
    if user.role == "student":
        class_name = db.scalar(
            select(SchoolClass.name).join(ClassStudent, ClassStudent.class_id == SchoolClass.id).where(ClassStudent.student_id == user.id)
        )
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "status": user.status,
        "teacher_types": teacher_responsibilities(db, user),
        "school": school.name if school else None,
        "class_name": class_name,
        "form": user.form,
        "avatar_url": user.avatar_url,
        "last_login_at": user.last_login_at,
    }


def _require_local() -> None:
    if get_settings().auth_mode != "local":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Handled by Supabase Auth")


def _find(db: Session, identifier: str) -> Profile | None:
    ident = identifier.strip().lower()
    column = Profile.email if "@" in ident else Profile.username
    return db.scalar(select(Profile).where(func.lower(column) == ident))


def _ip(request: Request) -> str:
    return audit.client_ip(request) or "unknown"


@router.get("/config")
def auth_config():
    s = get_settings()
    return {"mode": s.auth_mode, "ai_enabled": s.ai_enabled, "password_recovery": s.auth_mode}


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    s = get_settings()
    if s.auth_mode != "local" or not s.is_development:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    demo_emails = ["admin@school.demo", "aisyah@student.demo", "farid@teacher.demo", "tan@teacher.demo", "rohana@teacher.demo"]
    users = db.scalars(select(Profile).where(Profile.email.in_(demo_emails), Profile.status == "active"))
    order = {e: i for i, e in enumerate(demo_emails)}
    return sorted(
        ({"email": u.email, "full_name": u.full_name, "role": u.role, "teacher_types": teacher_responsibilities(db, u)} for u in users),
        key=lambda u: order[u["email"]],
    )


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    _require_local()
    s = get_settings()
    key = f"login:{_ip(request)}:{body.identifier.strip().lower()}"
    window = s.login_window_minutes * 60
    if limiter.blocked(key, s.login_max_failures, window):
        raise too_many()

    user = _find(db, body.identifier)
    cred = db.get(LocalCredential, user.id) if user else None
    if not passwords.verify_or_burn(body.password, cred):
        limiter.hit(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_CREDENTIALS)
    if not user.is_active:
        raise account_disabled()

    limiter.reset(key)
    user.last_login_at = utcnow()
    db.commit()
    token, ttl = create_access_token(user.id, cred)
    return {"access_token": token, "token_type": "bearer", "expires_in": ttl, "user": profile_payload(db, user)}


@router.get("/me")
def me(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_payload(db, user)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(body: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    _require_local()
    s = get_settings()
    limiter.check_and_hit(f"forgot:{_ip(request)}", 5, s.login_window_minutes * 60)
    user = _find(db, body.identifier)
    if user is not None and user.is_active:
        token = passwords.issue_reset_token(db, user)
        audit.record(db, "auth.password_reset_requested", "profile", user.id, actor=user, request=request, details={"via": "self_service"})
        db.commit()
        link = f"{s.frontend_url.rstrip('/')}/reset-password?token={token}"
        mailer.send_password_reset(user.email, user.full_name, link, s.password_reset_ttl_minutes)
    return {"message": RECOVERY_MESSAGE}


@router.post("/reset-password")
def reset_password(body: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    _require_local()
    limiter.check_and_hit(f"reset:{_ip(request)}", 10, get_settings().login_window_minutes * 60)
    if problems := passwords.password_problems(body.new_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(problems))
    user = passwords.consume_reset_token(db, body.token)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired. Please request a new one.")
    if problems := passwords.password_problems(body.new_password, (user.email, user.username)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(problems))
    passwords.set_password(db, user, body.new_password)
    audit.record(db, "auth.password_reset_completed", "profile", user.id, actor=user, request=request)
    db.commit()
    return {"message": "Your password has been reset. You can now sign in."}


@router.post("/change-password")
def change_password(body: ChangePasswordIn, request: Request, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_local()
    s = get_settings()
    key = f"change-password:{user.id}"
    if limiter.blocked(key, s.login_max_failures, s.login_window_minutes * 60):
        raise too_many()
    cred = db.get(LocalCredential, user.id)
    if not passwords.verify_or_burn(body.current_password, cred):
        limiter.hit(key)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your current password is incorrect")
    if problems := passwords.password_problems(body.new_password, (user.email, user.username)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, " ".join(problems))
    if body.new_password == body.current_password:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a password different from your current one.")
    limiter.reset(key)
    passwords.set_password(db, user, body.new_password)
    audit.record(db, "auth.password_changed", "profile", user.id, actor=user, request=request)
    db.commit()
    token, ttl = create_access_token(user.id, db.get(LocalCredential, user.id))
    return {"message": "Password updated.", "access_token": token, "expires_in": ttl}
