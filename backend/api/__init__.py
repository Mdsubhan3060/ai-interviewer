# api/__init__.py - Router registry
from fastapi import APIRouter

try:
    from api.auth import router as auth_router
except ImportError:
    auth_router = APIRouter()

try:
    from api.resume import router as resume_router
except ImportError:
    resume_router = APIRouter()

try:
    from api.job import router as job_router
except ImportError:
    job_router = APIRouter()

try:
    from api.interview import router as interview_router
except ImportError as e:
    print("INTERVIEW IMPORT ERROR:", e)
    raise e

try:
    from api.dashboard import router as dashboard_router
except ImportError:
    dashboard_router = APIRouter()

try:
    from api.audio import router as audio_router
except ImportError:
    audio_router = APIRouter()

try:
    from api.submit import router as submit_router
except ImportError:
    submit_router = APIRouter()

__all__ = [
    "auth_router", "resume_router", "job_router",
    "interview_router", "dashboard_router",
    "audio_router", "submit_router"
]
