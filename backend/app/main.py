from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .routers import ai, auth, community, exams, lessons, practice, quiz, students, subjects, teachers


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, subjects, lessons, quiz, students, practice, exams, teachers, community, ai):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "auth_mode": settings.auth_mode, "ai_enabled": bool(settings.openai_api_key)}
