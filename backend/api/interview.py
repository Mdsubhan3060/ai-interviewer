# api/interview.py — FIXED VERSION
# Combines start + submit + next + session endpoints
# Fixes: missing file, role/job_title mismatch, submit wiring

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID
import logging

from core.dependencies import get_current_user
from db.session import get_db
from db.models.user import User
from db.models.interview_session import InterviewSession, SessionStatus
from db.models.response import Response
from services.interview_service import start_interview_session, get_next_question
from services.evaluation_service import submit_answer

logger = logging.getLogger(__name__)
router = APIRouter()


class StartInterviewRequest(BaseModel):
    role: Optional[str] = None           # frontend sends "role"
    job_title: Optional[str] = None      # backend uses "job_title" — accept both
    company_name: Optional[str] = None
    job_description: Optional[str] = None
    interview_type: str = "mixed"
    total_questions: int = 5


class SubmitAnswerRequest(BaseModel):
    session_id: UUID
    question_number: int
    answer_text: str
    is_audio: bool = False
    stress_score: Optional[float] = None
    stress_signals: Optional[dict] = None
    latency_ms: int = 0


@router.post("/start")
async def start_interview(
    request: StartInterviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job_title = request.job_title or request.role  # accept both
    try:
        result = await start_interview_session(
            db=db, user=current_user,
            job_description=request.job_description,
            job_title=job_title,
            company_name=request.company_name,
            interview_type=request.interview_type,
            total_questions=max(1, min(20, request.total_questions)),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Start interview failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start interview.")


@router.post("/submit")
async def submit_answer_endpoint(
    request: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not request.answer_text.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty.")
    try:
        result = await submit_answer(
            db=db, session_id=request.session_id, user=current_user,
            question_number=request.question_number,
            answer_text=request.answer_text.strip(),
            is_audio=request.is_audio,
            stress_score=request.stress_score,
            stress_signals=request.stress_signals,
            latency_ms=request.latency_ms,
        )
        if result.get("session_complete"):
            try:
                from services.evaluation_service import trigger_memory_update
                await trigger_memory_update(db, request.session_id, current_user)
            except Exception as e:
                logger.error(f"Memory update failed (non-critical): {e}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Submit answer failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to evaluate answer.")


@router.get("/sessions/all")
async def get_all_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return {
        "total": len(sessions),
        "sessions": [
            {
                "id": str(s.id), "job_title": s.job_title,
                "company": s.company_name, "status": s.status,
                "overall_score": s.overall_score,
                "total_questions": s.total_questions,
                "date": s.created_at.isoformat(),
            }
            for s in sessions
        ],
    }


@router.get("/{session_id}/next")
async def next_question(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        question = await get_next_question(db, session_id, current_user.id)
        if question is None:
            return {
                "status": "completed",
                "completed": True,
                "message": "Interview complete!",
                "session_id": str(session_id),
            }
        return {
            "status": "in_progress",
            "completed": False,
            "session_id": str(session_id),
            **question,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{session_id}")
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    responses_result = await db.execute(
        select(Response).where(Response.session_id == session_id)
        .order_by(Response.question_number)
    )
    responses = responses_result.scalars().all()

    return {
        "session_id": str(session.id),
        "status": session.status,
        "job_title": session.job_title,
        "interview_type": session.interview_type,
        "total_questions": session.total_questions,
        "overall_score": session.overall_score,
        "questions": [
            {
                "number": r.question_number, "text": r.question_text,
                "category": r.question_category, "answered": r.answer_text is not None,
                "score": r.overall_score,
            }
            for r in responses
        ],
    }
