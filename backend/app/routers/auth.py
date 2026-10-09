from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import ClassStudent, Profile, School, SchoolClass
from ..schemas import DemoLoginIn
from ..security import create_demo_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
        "full_name": user.full_name,
        "role": user.role,
        "teacher_types": user.teacher_types or [],
        "school": school.name if school else None,
        "class_name": class_name,
        "form": user.form,
        "avatar_url": user.avatar_url,
    }


@router.get("/config")
def auth_config():
    s = get_settings()
    return {"mode": s.auth_mode, "ai_enabled": bool(s.openai_api_key)}


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    if get_settings().auth_mode != "demo":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    demo_emails = ["aisyah@student.demo", "farid@teacher.demo", "tan@teacher.demo", "rohana@teacher.demo"]
    users = db.scalars(select(Profile).where(Profile.email.in_(demo_emails)))
    order = {e: i for i, e in enumerate(demo_emails)}
    return sorted(
        ({"email": u.email, "full_name": u.full_name, "role": u.role, "teacher_types": u.teacher_types or []} for u in users),
        key=lambda u: order[u["email"]],
    )


@router.post("/demo-login")
def demo_login(body: DemoLoginIn, db: Session = Depends(get_db)):
    settings = get_settings()
    if settings.auth_mode != "demo":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo login is disabled; sign in with Supabase")
    user = db.scalar(select(Profile).where(Profile.email == body.email.strip().lower()))
    if user is None or body.password != settings.demo_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return {"access_token": create_demo_token(user.id), "token_type": "bearer", "user": profile_payload(db, user)}


@router.get("/me")
def me(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    return profile_payload(db, user)
