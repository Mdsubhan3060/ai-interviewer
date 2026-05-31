# ============================================
# api/audio.py
# ============================================
# WHY THIS FILE EXISTS:
# Handles the audio upload endpoint.
# When user records their answer:
#   1. Browser sends audio file to this endpoint
#   2. We transcribe it with Whisper
#   3. We analyze stress signals
#   4. Return transcribed text + stress data
#   5. Frontend then submits text answer to /interview/submit
# ============================================

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from core.dependencies import get_current_user
from db.session import get_db
from db.models.user import User
from services.audio_service import process_audio_answer
from services.stress_service import compute_stress_score

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# ENDPOINT: Transcribe Audio Answer
# POST /api/v1/audio/transcribe
# ============================================
@router.post("/transcribe")
async def transcribe_answer(
    file: Optional[UploadFile] = File(default=None),
    audio: Optional[UploadFile] = File(default=None),
    question_category: str = Form(default="technical"),
    latency_ms: int = Form(default=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Transcribe audio answer and analyze stress.

    Accepts:
    - file/audio: Audio file (mp3, wav, m4a, webm, ogg)
    - question_category: "technical" or "behavioral"
    - latency_ms: Time in ms between question shown and recording started

    Returns:
    - transcribed text
    - stress score and signals
    - recommended interviewer persona
    """

    upload = file or audio
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Audio upload is required. Send it as form field 'audio' or 'file'.",
        )

    # ---- Read Audio File ----
    file_bytes = await upload.read()

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty.",
        )

    logger.info(
        f"Received audio: {upload.filename} "
        f"({len(file_bytes)/1024:.1f}KB) "
        f"category={question_category} "
        f"latency={latency_ms}ms"
    )

    # ---- Transcribe ----
    try:
        transcription = await process_audio_answer(
            file_bytes=file_bytes,
            filename=upload.filename or "answer.wav",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Transcription failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed. Please try typing your answer instead.",
        )

    # ---- Stress Analysis ----
    stress_result = compute_stress_score(
        text=transcription["text"],
        duration_seconds=transcription.get("duration", 0),
        latency_ms=latency_ms,
        question_category=question_category,
    )

    # ---- Return Everything ----
    return {
        # Transcription
        "transcribed_text": transcription["text"],
        "transcription": transcription["text"],
        "audio_duration_seconds": transcription.get("duration", 0),
        "language_detected": transcription.get("language", "en"),

        # Stress Analysis
        "stress_score": stress_result["stress_score"],
        "stress_signals": stress_result["signals"],

        # Persona (what interviewer should do next)
        "interviewer_persona": stress_result["persona"],
        "persona": stress_result["persona"],
        "persona_name": stress_result["persona_details"]["name"],
        "persona_tone": stress_result["persona_details"]["tone"],

        # Helpful feedback for the user
        "stress_feedback": _get_stress_feedback(
            stress_result["stress_score"],
            stress_result["signals"],
        ),
    }


# ============================================
# Helper: Generate Human-Readable Stress Feedback
# ============================================
def _get_stress_feedback(stress_score: float, signals: dict) -> list[str]:
    """
    Generate friendly feedback tips based on stress signals.
    Shown to user after they answer, before evaluation.
    """
    feedback = []

    # Filler words feedback
    filler_rate = signals.get("filler_rate", 0)
    if filler_rate > 5:
        feedback.append(
            f"You used {signals.get('filler_count', 0)} filler words "
            f"(um, uh, like). Try pausing silently instead."
        )
    elif filler_rate > 2:
        feedback.append(
            "A few filler words detected. "
            "Slow down slightly to reduce them."
        )

    # Hedge words feedback
    hedge_count = signals.get("hedge_count", 0)
    if hedge_count > 3:
        feedback.append(
            f"You used {hedge_count} hedging phrases (I think, maybe, not sure). "
            "Speak more confidently — even if uncertain, state your view directly."
        )

    # WPM feedback
    wpm = signals.get("words_per_minute", 0)
    if wpm > 0:
        if wpm < 90:
            feedback.append(
                f"You spoke at {wpm:.0f} words/min — quite slow. "
                "Try to maintain a natural conversational pace."
            )
        elif wpm > 190:
            feedback.append(
                f"You spoke at {wpm:.0f} words/min — quite fast. "
                "Slow down to sound more confident and clear."
            )

    # Brevity feedback
    word_count = signals.get("word_count", 0)
    if word_count < 30:
        feedback.append(
            "Your answer was very brief. "
            "Try to elaborate more with examples and context."
        )

    # All good
    if not feedback and stress_score <= 3:
        feedback.append(
            "Great delivery! You sounded confident and clear."
        )

    return feedback
