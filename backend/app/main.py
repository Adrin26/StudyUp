from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import (
    admin,
    admin_classes,
    admin_school,
    admin_users,
    ai,
    auth,
    community,
    exams,
    lessons,
    practice,
    quiz,
    students,
    subjects,
    teachers,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, admin, admin_users, admin_school, admin_classes, subjects, lessons, quiz, students, practice, exams, teachers, community, ai):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "auth_mode": settings.auth_mode, "ai_enabled": settings.ai_enabled}
