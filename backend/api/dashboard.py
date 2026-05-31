# ============================================
# api/dashboard.py
# ============================================
# WHY THIS FILE EXISTS:
# Exposes dashboard data to the React frontend.
#
# Endpoints:
#   GET /api/v1/dashboard/summary    → main dashboard page data
#   GET /api/v1/dashboard/session/{id} → single session detail
#
# The frontend Dashboard.jsx calls /api/v1/dashboard/summary.
# ============================================

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from core.dependencies import get_current_user
from db.models.user import User
from services.dashboard_service import get_dashboard_summary, get_session_detail

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# GET /summary
# ============================================
@router.get("/summary")
async def dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns everything needed for the main dashboard page.

    Response includes:
    - Running averages (overall, technical, communication, etc.)
    - Score history list (for the line chart)
    - Top weaknesses and strengths
    - GPT-generated recommendations
    - Last 10 completed sessions

    Frontend: src/pages/Dashboard.jsx → dashboardApi.getSummary()
    """
    try:
        data = await get_dashboard_summary(db=db, user_id=current_user.id)
        return data
    except Exception as e:
        logger.error(f"Dashboard summary failed: {e}")
        raise HTTPException(status_code=500, detail="Could not load dashboard data.")


# ============================================
# GET /session/{session_id}
# ============================================
@router.get("/session/{session_id}")
async def session_detail(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns full detail for one completed session.
    Includes all questions, answers, scores, and feedback.

    Used for "review past session" feature.
    """
    data = await get_session_detail(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    if not data:
        raise HTTPException(
            status_code=404,
            detail="Session not found or you don't have access to it.",
        )
    return data


# ============================================
# GET /history
# ============================================
@router.get("/history")
async def session_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns just the session history list.
    Lighter version of /summary for the history table.
    """
    try:
        data = await get_dashboard_summary(db=db, user_id=current_user.id)
        return {"sessions": data.get("session_history", [])}
    except Exception as e:
        logger.error(f"Session history failed: {e}")
        raise HTTPException(status_code=500, detail="Could not load session history.")
