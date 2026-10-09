import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .database import SessionLocal, engine, init_db
from .routers import (
    admin,
    admin_classes,
    admin_content,
    admin_school,
    admin_users,
    ai,
    auth,
    calendar,
    community,
    exams,
    gamification,
    lessons,
    memos,
    notifications,
    practice,
    quiz,
    students,
    subjects,
    teachers,
)
from .services.gamification import ensure_badges


log = logging.getLogger("minda")


def _ensure_reference_data() -> None:
    with SessionLocal() as db:
        try:
            ensure_badges(db)
            db.commit()
        except SQLAlchemyError:
            log.warning("Could not check badge definitions; is the database migrated?")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    _ensure_reference_data()
    yield


settings = get_settings()
production = settings.environment == "production"
app = FastAPI(
    title=settings.app_name,
    version="0.7.0",
    lifespan=lifespan,
    docs_url=None if production else "/docs",
    redoc_url=None if production else "/redoc",
    openapi_url=None if production else "/openapi.json",
)
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    path = request.url.path
    if path.startswith("/uploads/") or "/attachments/" in path:
        h.setdefault("Content-Security-Policy", "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox")
    if path.startswith("/api/"):
        h.setdefault("Cache-Control", "no-store")
    if production:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, admin, admin_users, admin_school, admin_classes, admin_content, memos, subjects, lessons, quiz, students, practice, exams, teachers, community, notifications, calendar, gamification, ai):
    app.include_router(r.router)
app.include_router(exams.student_router)


@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse({"status": "error", "database": "unreachable"}, status_code=503)
    return {"status": "ok", "database": "ok", "auth_mode": settings.auth_mode, "ai_enabled": settings.ai_enabled}
