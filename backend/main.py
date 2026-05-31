# backend/main.py — FIXED VERSION
# Changes: added audio_router registration

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from core.config import settings
from db.session import init_db

from api import (
    resume_router,
    job_router,
    interview_router,
    dashboard_router,
    auth_router,
    audio_router,
)

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.APP_NAME} in {settings.APP_ENV} mode")

    logger.info("STEP 1: About to connect DB")
    await init_db()
    logger.info("STEP 2: DB connection completed")

    logger.info("✅ Database connected")

    yield

    logger.info("👋 Shutting down gracefully")
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered job matching and adaptive mock interview coaching",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(auth_router,      prefix=f"{API_PREFIX}/auth",      tags=["Auth"])
app.include_router(resume_router,    prefix=f"{API_PREFIX}/resume",    tags=["Resume"])
app.include_router(job_router,       prefix=f"{API_PREFIX}/job",       tags=["Job"])
app.include_router(interview_router, prefix=f"{API_PREFIX}/interview", tags=["Interview"])
app.include_router(dashboard_router, prefix=f"{API_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(audio_router,     prefix=f"{API_PREFIX}/audio",     tags=["Audio"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "version": "1.0.0"}


@app.get("/", tags=["Root"])
async def root():
    return {"message": f"Welcome to {settings.APP_NAME} API"}
