# ============================================
# api/submit.py
# ============================================
# WHY THIS FILE EXISTS:
# One endpoint to handle answer submission.
# Works for BOTH text and audio answers.
#
# For text answers:
#   → stress computed here from text
#
# For audio answers:
#   → audio already transcribed via /audio/transcribe
#   → stress already computed there
#   → frontend passes transcribed text + stress data here
# ============================================

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
import logging

from core.dependencies import get_current_user
from db.session import get_db
from db.models.user import User
from services.evaluation_service import submit_answer

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# Request Schema
# ============================================
class SubmitAnswerRequest(BaseModel):
    session_id: UUID
    question_number: int
    answer_text: str

    # Audio-specific fields (optional)
    # If is_audio=True, pass stress data from /audio/transcribe response
    is_audio: bool = False
    stress_score: Optional[float] = None
    stress_signals: Optional[dict] = None
    latency_ms: int = 0          # ms between question shown → answer started


# ============================================
# ENDPOINT: Submit Answer
# POST /api/v1/interview/submit
# ============================================
@router.post("/submit")
async def submit_answer_endpoint(
    request: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an answer to an interview question.

    Works for both text and audio answers.

    For text answers:
        Just send answer_text. Stress computed automatically.

    For audio answers:
        1. First call POST /audio/transcribe → get transcribed_text + stress data
        2. Then call this endpoint with:
           - answer_text = transcribed_text
           - is_audio = True
           - stress_score = from transcribe response
           - stress_signals = from transcribe response

    Returns evaluation with scores, feedback, and ideal answer.
    """

    # Validate answer not empty
    if not request.answer_text or not request.answer_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answer cannot be empty.",
        )

    # Validate question number
    if request.question_number < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question number must be 1 or higher.",
        )

    try:
        result = await submit_answer(
            db=db,
            session_id=request.session_id,
            user=current_user,
            question_number=request.question_number,
            answer_text=request.answer_text.strip(),
            is_audio=request.is_audio,
            stress_score=request.stress_score,
            stress_signals=request.stress_signals,
            latency_ms=request.latency_ms,
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Answer submission failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate answer. Please try again.",
        )
