# ============================================
# services/dashboard_service.py
# ============================================
# WHY THIS FILE EXISTS:
# The dashboard needs data from multiple tables:
#   - WeaknessSummary  (running averages, weak areas)
#   - InterviewSessions (history, scores per session)
#   - Responses         (per-question breakdown)
#
# Instead of doing all these queries inside the API endpoint,
# we put them here. Same reason as every other service:
#   API = receive request / send response
#   Service = do the actual work
# ============================================

import logging
from uuid import UUID
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.weakness_summary import WeaknessSummary
from db.models.interview_session import InterviewSession, SessionStatus
from db.models.response import Response

logger = logging.getLogger(__name__)


# ============================================
# FUNCTION 1: Get Dashboard Summary
# ============================================
async def get_dashboard_summary(
    db: AsyncSession,
    user_id: UUID,
) -> dict:
    """
    Returns everything needed for the main dashboard page.

    Combines:
    - WeaknessSummary (running averages, weak/strong areas,
                       score history, recommendations)
    - Recent session list (for history table)

    Args:
        db: Database session
        user_id: Current user's ID

    Returns:
        Dict with all dashboard data
    """

    # ---- Get WeaknessSummary ----
    summary_result = await db.execute(
        select(WeaknessSummary).where(WeaknessSummary.user_id == user_id)
    )
    summary = summary_result.scalar_one_or_none()

    # ---- Get Completed Sessions ----
    completed_sessions_result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.status.in_([
                SessionStatus.COMPLETED.value,
                str(SessionStatus.COMPLETED),
            ]),
        )
        .order_by(InterviewSession.created_at)
    )
    completed_sessions = completed_sessions_result.scalars().all()
    recent_sessions = list(reversed(completed_sessions[-10:]))

    # ---- Build Session History ----
    session_history = []
    for s in recent_sessions:
        session_history.append({
            "id": str(s.id),
            "date": s.created_at.isoformat(),
            "job_title": s.job_title or "General Interview",
            "overall_score": s.overall_score,
            "total_questions": s.total_questions,
            "category_scores": s.category_scores or {},
            "avg_stress_score": s.avg_stress_score,
            "dominant_persona": s.dominant_persona,
        })

    def avg(scores):
        valid = [score for score in scores if score is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    def category_avg(category: str):
        return avg([
            (session.category_scores or {}).get(category)
            for session in completed_sessions
        ])

    fallback_overall_avg = avg([s.overall_score for s in completed_sessions])
    fallback_technical_avg = category_avg("technical")
    fallback_communication_avg = category_avg("communication")
    fallback_confidence_avg = category_avg("confidence")
    fallback_relevance_avg = category_avg("relevance")
    fallback_stress_avg = avg([s.avg_stress_score for s in completed_sessions])

    score_history = [
        s.overall_score
        for s in completed_sessions
        if s.overall_score is not None
    ][-20:]

    category_score_history = {
        "technical": [],
        "communication": [],
        "confidence": [],
        "relevance": [],
    }
    for session in completed_sessions[-20:]:
        scores = session.category_scores or {}
        category_score_history["technical"].append(scores.get("technical") or 0)
        category_score_history["communication"].append(scores.get("communication") or 0)
        category_score_history["confidence"].append(scores.get("confidence") or 0)
        category_score_history["relevance"].append(scores.get("relevance") or 0)

    top_weaknesses = []
    top_strengths = []
    technical_avg = summary.technical_avg if summary else fallback_technical_avg
    communication_avg = summary.communication_avg if summary else fallback_communication_avg
    confidence_avg = summary.confidence_avg if summary else fallback_confidence_avg
    relevance_avg = summary.relevance_avg if summary else fallback_relevance_avg

    score_map = {
        "technical_depth": technical_avg,
        "communication": communication_avg,
        "confidence": confidence_avg,
        "relevance": relevance_avg,
    }
    sorted_scores = sorted(
        ((name, score) for name, score in score_map.items() if score is not None),
        key=lambda item: item[1],
    )
    top_weaknesses = [name for name, score in sorted_scores if score < 6.0][:3]
    top_strengths = [name for name, score in sorted_scores if score >= 7.5][-3:]

    # ---- No sessions yet ----
    if not summary and not completed_sessions:
        return {
            "total_sessions": 0,
            "total_questions_answered": 0,
            "overall_avg": None,
            "technical_avg": None,
            "communication_avg": None,
            "confidence_avg": None,
            "relevance_avg": None,
            "avg_stress_score": None,
            "stress_trend": None,
            "top_weaknesses": [],
            "top_strengths": [],
            "score_history": [],
            "category_score_history": {},
            "recommendations": [],
            "session_history": session_history,
        }

    # ---- Return Full Dashboard Data ----
    return {
        # Counts
        "total_sessions": summary.total_sessions if summary else len(completed_sessions),
        "total_questions_answered": (
            summary.total_questions_answered
            if summary
            else sum(s.total_questions or 0 for s in completed_sessions)
        ),

        # Running averages (0-10)
        "overall_avg": summary.overall_avg if summary else fallback_overall_avg,
        "technical_avg": technical_avg,
        "communication_avg": communication_avg,
        "confidence_avg": confidence_avg,
        "relevance_avg": relevance_avg,

        # Stress
        "avg_stress_score": summary.avg_stress_score if summary else fallback_stress_avg,
        "stress_trend": summary.stress_trend if summary else None,

        # Weak / strong areas
        "top_weaknesses": (summary.top_weaknesses if summary and summary.top_weaknesses else top_weaknesses),
        "top_strengths": (summary.top_strengths if summary and summary.top_strengths else top_strengths),

        # Chart data
        "score_history": summary.score_history if summary and summary.score_history else score_history,
        "category_score_history": (
            summary.category_score_history
            if summary and summary.category_score_history
            else category_score_history
        ),

        # GPT recommendations
        "recommendations": summary.recommendations if summary and summary.recommendations else [],

        # Session list
        "session_history": session_history,
    }


# ============================================
# FUNCTION 2: Get Session Detail
# ============================================
async def get_session_detail(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
) -> Optional[dict]:
    """
    Returns full detail for one session including
    all questions and answers.

    Used for the "review this session" feature.

    Args:
        db: Database session
        session_id: Session to retrieve
        user_id: Must match session owner

    Returns:
        Dict with session + all Q&A pairs, or None
    """

    # Get session
    session_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user_id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        return None

    # Get all responses for this session
    responses_result = await db.execute(
        select(Response)
        .where(Response.session_id == session_id)
        .order_by(Response.question_number)
    )
    responses = responses_result.scalars().all()

    qa_pairs = []
    for r in responses:
        qa_pairs.append({
            "question_number": r.question_number,
            "question_text": r.question_text,
            "question_category": r.question_category,
            "question_difficulty": r.question_difficulty,
            "answer_text": r.answer_text,
            "overall_score": r.overall_score,
            "relevance_score": r.relevance_score,
            "clarity_score": r.clarity_score,
            "confidence_score": r.confidence_score,
            "technical_score": r.technical_score,
            "strengths": r.strengths or [],
            "weaknesses": r.weaknesses or [],
            "ideal_answer": r.ideal_answer,
            "coaching_tip": r.coaching_tip,
            "stress_score": r.stress_score,
            "interviewer_persona": r.interviewer_persona,
            "is_audio_answer": r.is_audio_answer,
        })

    return {
        "id": str(session.id),
        "date": session.created_at.isoformat(),
        "job_title": session.job_title or "General Interview",
        "status": session.status,
        "overall_score": session.overall_score,
        "total_questions": session.total_questions,
        "category_scores": session.category_scores or {},
        "avg_stress_score": session.avg_stress_score,
        "targeted_weaknesses": session.targeted_weaknesses or [],
        "qa_pairs": qa_pairs,
    }
