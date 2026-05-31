# ============================================
# api/job.py
# ============================================

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from core.dependencies import get_current_user
from db.session import get_db
from db.models.user import User
from services.job_service import match_job, get_match_history

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# Request Schema
# ============================================
class JobMatchRequest(BaseModel):
    job_description: str
    job_title: Optional[str] = None
    company_name: Optional[str] = None


# ============================================
# ENDPOINT 1: Match Job
# POST /api/v1/job/match
# ============================================
@router.post("/match")
async def match_job_endpoint(
    request: JobMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Match resume against a job description.
    Returns score 0-100 + matched/missing skills.
    """

    # Validate job description length
    if len(request.job_description.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job description too short. Please paste the full job posting.",
        )

    try:
        result = await match_job(
            db=db,
            user=current_user,
            job_description=request.job_description,
            job_title=request.job_title,
            company_name=request.company_name,
        )

        # ---- Score Label ----
        # Give the score a human-readable label
        score = result.match_score
        if score >= 80:
            label = "Excellent Match 🎯"
        elif score >= 65:
            label = "Good Match ✅"
        elif score >= 50:
            label = "Moderate Match 🟡"
        else:
            label = "Weak Match ❌"

        return {
            "match_id": str(result.id),
            "score": score,
            "label": label,
            "matched_skills": result.matched_skills,
            "missing_skills": result.missing_skills,
            "bonus_skills": result.bonus_skills,
            "experience_match": result.experience_match,
            "education_match": result.education_match,
            "summary": result.match_summary,
            "job_title": result.job_title,
            "company": result.company_name,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Job matching failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job matching failed. Please try again.",
        )


# ============================================
# ENDPOINT 2: Match History
# GET /api/v1/job/history
# ============================================
@router.get("/history")
async def get_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user's recent job matches."""
    matches = await get_match_history(db, current_user.id)

    return {
        "total": len(matches),
        "matches": [
            {
                "id": str(m.id),
                "job_title": m.job_title,
                "company": m.company_name,
                "score": m.match_score,
                "matched_skills_count": len(m.matched_skills or []),
                "missing_skills_count": len(m.missing_skills or []),
                "date": m.created_at.isoformat(),
            }
            for m in matches
        ]
    }


# ============================================
# ENDPOINT 3: Get Single Match
# GET /api/v1/job/match/{match_id}
# ============================================
@router.get("/match/{match_id}")
async def get_match(
    match_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full details of a specific job match."""
    from sqlalchemy import select
    from db.models.job_match import JobMatch
    from uuid import UUID

    result = await db.execute(
        select(JobMatch).where(
            JobMatch.id == UUID(match_id),
            JobMatch.user_id == current_user.id,
        )
    )
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    return {
        "id": str(match.id),
        "job_title": match.job_title,
        "company": match.company_name,
        "score": match.match_score,
        "matched_skills": match.matched_skills,
        "missing_skills": match.missing_skills,
        "bonus_skills": match.bonus_skills,
        "experience_match": match.experience_match,
        "education_match": match.education_match,
        "summary": match.match_summary,
        "cover_letter": match.cover_letter,
        "date": match.created_at.isoformat(),
    }
