# ============================================
# services/memory_service.py
# ============================================
# WHY THIS FILE EXISTS:
# This is the BRAIN that remembers everything.
#
# After every completed interview session,
# this service:
#   1. Reads all scores from that session
#   2. Updates running averages in WeaknessSummary
#   3. Identifies top weak areas
#   4. Calculates improvement trend
#   5. Generates new recommendations if needed
#
# WHY RUNNING AVERAGES?
# Session 1: technical = 4.0
# Session 2: technical = 5.0
# Session 3: technical = 7.0
# Running average = (4+5+7)/3 = 5.33
# Trend = improving ✅
#
# This powers TWO features:
# 1. Dashboard: "Your technical score improved from 4 to 7"
# 2. Adaptive Interview: "You're weak in technical — 
#    here are 3 extra technical questions"
#
# HOW RUNNING AVERAGE WORKS:
# We don't store ALL scores (would grow forever).
# We use an incremental formula:
#   new_avg = (old_avg * old_count + new_value) / new_count
# This lets us update without recalculating everything.
# ============================================

import json
import logging
from uuid import UUID
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncAzureOpenAI

from core.config import settings
from db.models.interview_session import InterviewSession, SessionStatus
from db.models.response import Response
from db.models.weakness_summary import WeaknessSummary
from db.models.user import User

logger = logging.getLogger(__name__)

openai_client = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version=settings.AZURE_OPENAI_API_VERSION,
)

# How many sessions before we regenerate recommendations
RECOMMENDATION_REFRESH_INTERVAL = 3


# ============================================
# FUNCTION 1: Update Running Average
# ============================================
def update_running_average(
    old_avg: Optional[float],
    old_count: int,
    new_value: float,
) -> float:
    """
    Update a running average with a new value.

    WHY THIS FORMULA?
    We can't store every score forever.
    This formula updates the average incrementally:

    Example:
        old_avg = 5.0, old_count = 3, new_value = 7.0
        new_count = 4
        new_avg = (5.0 * 3 + 7.0) / 4 = 5.5

    Args:
        old_avg: Previous average (None if first session)
        old_count: How many sessions contributed to old_avg
        new_value: New score to include

    Returns:
        Updated average
    """
    if old_avg is None or old_count == 0:
        return round(new_value, 2)

    new_count = old_count + 1
    new_avg = (old_avg * old_count + new_value) / new_count
    return round(new_avg, 2)


# ============================================
# FUNCTION 2: Identify Weak Areas
# ============================================
def identify_weak_areas(
    technical_avg: Optional[float],
    communication_avg: Optional[float],
    confidence_avg: Optional[float],
    relevance_avg: Optional[float],
) -> tuple[list[str], list[str]]:
    """
    Identify top weaknesses and strengths.

    Threshold: below 6.0 = weak area
    Threshold: above 7.5 = strong area

    Args:
        technical_avg: Average technical score
        communication_avg: Average communication score
        confidence_avg: Average confidence score
        relevance_avg: Average relevance score

    Returns:
        Tuple of (weak_areas, strong_areas) as lists of strings
    """
    scores = {
        "technical_depth": technical_avg or 0,
        "communication": communication_avg or 0,
        "confidence": confidence_avg or 0,
        "relevance": relevance_avg or 0,
    }

    # Sort by score
    sorted_scores = sorted(scores.items(), key=lambda x: x[1])

    # Weak = bottom scores below 6.0
    weak_areas = [
        area for area, score in sorted_scores
        if score < 6.0
    ][:3]  # Max 3 weak areas

    # Strong = top scores above 7.5
    strong_areas = [
        area for area, score in sorted_scores
        if score >= 7.5
    ][-3:]  # Top 3 strong areas

    return weak_areas, strong_areas


# ============================================
# FUNCTION 3: Calculate Stress Trend
# ============================================
def calculate_stress_trend(score_history: list[float]) -> float:
    """
    Calculate if stress is improving over time.

    Compares last 3 sessions to previous 3 sessions.
    Positive = getting LESS stressed (improving)
    Negative = getting MORE stressed (worsening)

    Args:
        score_history: List of stress scores chronologically

    Returns:
        Trend value (positive = improving)
    """
    if len(score_history) < 4:
        return 0.0  # Not enough data

    # Split into recent and older
    midpoint = len(score_history) // 2
    older = score_history[:midpoint]
    recent = score_history[midpoint:]

    older_avg = sum(older) / len(older)
    recent_avg = sum(recent) / len(recent)

    # Positive trend = stress DECREASED (recent < older)
    trend = round(older_avg - recent_avg, 2)
    return trend


# ============================================
# FUNCTION 4: Generate Recommendations With GPT
# ============================================
async def generate_recommendations(
    weak_areas: list[str],
    strong_areas: list[str],
    total_sessions: int,
    category_scores: dict,
) -> list[str]:
    """
    Generate personalized improvement recommendations.

    Called every RECOMMENDATION_REFRESH_INTERVAL sessions.
    Uses GPT to generate specific, actionable advice
    based on the user's actual weak areas.

    Args:
        weak_areas: List of weak category names
        strong_areas: List of strong category names
        total_sessions: Total sessions completed
        category_scores: Dict of category averages

    Returns:
        List of 3-5 recommendation strings
    """
    if not weak_areas:
        return [
            "Excellent performance across all areas!",
            "Consider attempting harder difficulty interviews.",
            "Practice system design questions for senior roles.",
        ]

    prompt = f"""
You are a career coach analyzing interview performance data.

Performance Summary:
- Total sessions completed: {total_sessions}
- Weak areas: {', '.join(weak_areas)}
- Strong areas: {', '.join(strong_areas) if strong_areas else 'None identified yet'}
- Scores: {json.dumps(category_scores, indent=2)}

Generate 3-5 SPECIFIC, ACTIONABLE improvement recommendations.

RESPOND ONLY WITH A JSON ARRAY OF STRINGS. No explanations, no markdown.

["recommendation 1", "recommendation 2", "recommendation 3"]

Rules:
- Each recommendation must be specific and actionable
- Reference the actual weak areas
- Include specific resources or techniques
- Keep each recommendation under 2 sentences
- Prioritize the weakest areas first
"""

    try:
        response = await openai_client.chat.completions.create(
            model=settings.AZURE_OPENAI_MINI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.5,
        )

        response_text = response.choices[0].message.content.strip()
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        recommendations = json.loads(response_text)
        return recommendations if isinstance(recommendations, list) else []

    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}")
        # Fallback recommendations based on weak areas
        fallbacks = []
        if "technical_depth" in weak_areas:
            fallbacks.append(
                "Practice explaining technical concepts out loud. "
                "Use LeetCode or System Design Primer for structured practice."
            )
        if "confidence" in weak_areas:
            fallbacks.append(
                "Record yourself answering questions and review the playback. "
                "Practice power poses before interviews to build confidence."
            )
        if "communication" in weak_areas:
            fallbacks.append(
                "Structure answers using the STAR method: "
                "Situation, Task, Action, Result."
            )
        if "relevance" in weak_areas:
            fallbacks.append(
                "Before answering, pause and identify the core of what's being asked. "
                "Answer that specific question before adding context."
            )
        return fallbacks or ["Keep practicing — consistency is key!"]


# ============================================
# FUNCTION 5: Update Memory After Session
# ============================================
async def update_memory_after_session(
    db: AsyncSession,
    session_id: UUID,
    user: User,
) -> WeaknessSummary:
    """
    Main function — updates WeaknessSummary after a completed session.

    Called automatically when a session is marked COMPLETED
    in evaluation_service.py.

    Steps:
    1. Get session + all responses
    2. Calculate this session's category scores
    3. Get or create WeaknessSummary for user
    4. Update running averages
    5. Update score history (for charts)
    6. Identify new weak/strong areas
    7. Calculate stress trend
    8. Generate new recommendations if needed
    9. Save everything

    Args:
        db: Database session
        session_id: Completed session ID
        user: Current user

    Returns:
        Updated WeaknessSummary
    """

    # ---- Step 1: Get Session + Responses ----
    session_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user.id,
        )
    )
    session = session_result.scalar_one_or_none()

    if not session or session.status != SessionStatus.COMPLETED:
        raise ValueError("Session not found or not completed yet.")

    responses_result = await db.execute(
        select(Response).where(
            Response.session_id == session_id,
            Response.overall_score != None,
        )
    )
    responses = responses_result.scalars().all()

    if not responses:
        logger.warning(f"No scored responses found for session {session_id}")
        return None

    # ---- Step 2: Calculate This Session's Averages ----
    def safe_avg(scores):
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    session_scores = {
        "overall": safe_avg([r.overall_score for r in responses]),
        "technical": safe_avg([r.technical_score for r in responses]),
        "clarity": safe_avg([r.clarity_score for r in responses]),
        "confidence": safe_avg([r.confidence_score for r in responses]),
        "relevance": safe_avg([r.relevance_score for r in responses]),
        "stress": safe_avg([r.stress_score for r in responses]),
    }

    # Communication = average of clarity + confidence
    if session_scores["clarity"] and session_scores["confidence"]:
        session_scores["communication"] = round(
            (session_scores["clarity"] + session_scores["confidence"]) / 2, 2
        )

    logger.info(f"Session scores: {session_scores}")

    # ---- Step 3: Get or Create WeaknessSummary ----
    summary_result = await db.execute(
        select(WeaknessSummary).where(WeaknessSummary.user_id == user.id)
    )
    summary = summary_result.scalar_one_or_none()

    if not summary:
        # First session — create new summary
        summary = WeaknessSummary(
            user_id=user.id,
            total_sessions=0,
            total_questions_answered=0,
            score_history=[],
            category_score_history={
                "technical": [],
                "communication": [],
                "confidence": [],
                "relevance": [],
            },
            recommendations=[],
        )
        db.add(summary)
        await db.flush()
        logger.info(f"Created new WeaknessSummary for user {user.id}")

    old_count = summary.total_sessions

    # ---- Step 4: Update Running Averages ----
    summary.overall_avg = update_running_average(
        summary.overall_avg, old_count,
        session_scores["overall"] or 0,
    )
    summary.technical_avg = update_running_average(
        summary.technical_avg, old_count,
        session_scores["technical"] or 0,
    )
    summary.communication_avg = update_running_average(
        summary.communication_avg, old_count,
        session_scores.get("communication") or 0,
    )
    summary.confidence_avg = update_running_average(
        summary.confidence_avg, old_count,
        session_scores["confidence"] or 0,
    )
    summary.relevance_avg = update_running_average(
        summary.relevance_avg, old_count,
        session_scores["relevance"] or 0,
    )
    summary.avg_stress_score = update_running_average(
        summary.avg_stress_score, old_count,
        session_scores["stress"] or 5.0,
    )

    # ---- Step 5: Update Score History ----
    # Append this session's overall score to history list
    # Keep last 20 sessions max (enough for charts)
    score_history = list(summary.score_history or [])
    score_history.append(session_scores["overall"] or 0)
    summary.score_history = score_history[-20:]  # Keep last 20

    # Update per-category history
    cat_history = dict(summary.category_score_history or {})
    for cat in ["technical", "communication", "confidence", "relevance"]:
        if cat not in cat_history:
            cat_history[cat] = []
        cat_history[cat].append(session_scores.get(cat) or 0)
        cat_history[cat] = cat_history[cat][-20:]  # Keep last 20
    summary.category_score_history = cat_history

    # ---- Step 6: Update Counts ----
    summary.total_sessions = old_count + 1
    summary.total_questions_answered += len(responses)

    # ---- Step 7: Identify Weak/Strong Areas ----
    weak_areas, strong_areas = identify_weak_areas(
        technical_avg=summary.technical_avg,
        communication_avg=summary.communication_avg,
        confidence_avg=summary.confidence_avg,
        relevance_avg=summary.relevance_avg,
    )
    summary.top_weaknesses = weak_areas
    summary.top_strengths = strong_areas

    # ---- Step 8: Calculate Stress Trend ----
    stress_history = [
        s for s in score_history if s is not None
    ]
    summary.stress_trend = calculate_stress_trend(stress_history)

    # ---- Step 9: Generate Recommendations ----
    # Only regenerate every N sessions (cost control)
    sessions_since_refresh = (
        summary.total_sessions - summary.last_recommendation_session
    )
    if sessions_since_refresh >= RECOMMENDATION_REFRESH_INTERVAL:
        logger.info("Generating new recommendations...")
        summary.recommendations = await generate_recommendations(
            weak_areas=weak_areas,
            strong_areas=strong_areas,
            total_sessions=summary.total_sessions,
            category_scores={
                "technical": summary.technical_avg,
                "communication": summary.communication_avg,
                "confidence": summary.confidence_avg,
                "relevance": summary.relevance_avg,
            },
        )
        summary.last_recommendation_session = summary.total_sessions

    await db.flush()
    logger.info(
        f"✅ Memory updated for user {user.id} | "
        f"sessions={summary.total_sessions} | "
        f"weak={weak_areas} | "
        f"overall_avg={summary.overall_avg}"
    )

    return summary


# ============================================
# FUNCTION 6: Get User Memory
# ============================================
async def get_user_memory(
    db: AsyncSession,
    user_id: UUID,
) -> Optional[WeaknessSummary]:
    """
    Get user's WeaknessSummary.
    Returns None if user has no sessions yet.
    """
    result = await db.execute(
        select(WeaknessSummary).where(WeaknessSummary.user_id == user_id)
    )
    return result.scalar_one_or_none()
