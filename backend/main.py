from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from db.session import init_db
from api.auth import router as auth_router
from api.resume import router as resume_router
from api.job import router as job_router
from api.interview import router as interview_router
from api.dashboard import router as dashboard_router
from api.audio import router as audio_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s in %s mode", settings.APP_NAME, settings.APP_ENV)
    await init_db()
    logger.info("Database connected")
    yield
    logger.info("Shutting down gracefully")


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

app.include_router(auth_router, prefix=f"{API_PREFIX}/auth", tags=["Auth"])
app.include_router(resume_router, prefix=f"{API_PREFIX}/resume", tags=["Resume"])
app.include_router(job_router, prefix=f"{API_PREFIX}/job", tags=["Job"])
app.include_router(interview_router, prefix=f"{API_PREFIX}/interview", tags=["Interview"])
app.include_router(dashboard_router, prefix=f"{API_PREFIX}/dashboard", tags=["Dashboard"])
app.include_router(audio_router, prefix=f"{API_PREFIX}/audio", tags=["Audio"])


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "app": settings.APP_NAME, "version": "1.0.0"}


@app.get("/", tags=["Root"])
async def root():
    return {"message": f"Welcome to {settings.APP_NAME} API"}
