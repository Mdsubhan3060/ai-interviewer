# ============================================
# services/evaluation_service.py
# ============================================
# WHY THIS FILE EXISTS:
# After the user answers a question, we need to
# evaluate HOW WELL they answered it.
#
# This file does 3 things:
#   1. Sends answer to GPT for evaluation
#   2. Parses scores (relevance, clarity, confidence, technical)
#   3. Updates the Response row + InterviewSession in DB
#
# WHY GPT FOR EVALUATION?
# Rule-based scoring can't judge answer quality.
# "I used PostgreSQL" scores the same as
# "I chose PostgreSQL over MySQL because of JSONB
#  support and better concurrent write performance"
# — both mention PostgreSQL but quality is different.
# GPT understands the QUALITY of the answer.
#
# COST CONTROL:
# We use gpt-4o-mini (cheaper) for evaluation.
# GPT-4 is saved for question generation + cover letters.
# Evaluation is repetitive structured extraction —
# gpt-4o-mini handles this perfectly.
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
from services.stress_service import compute_stress_score, get_persona_prompt

logger = logging.getLogger(__name__)

openai_client = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version=settings.AZURE_OPENAI_API_VERSION,
)


# ============================================
# FUNCTION 1: Evaluate Answer With GPT
# ============================================
async def evaluate_answer_with_gpt(
    question: str,
    answer: str,
    question_category: str,
    question_difficulty: str,
    job_title: str,
    persona_prompt: str,
    resume_context: str = "",
) -> dict:
    """
    Send question + answer to GPT for evaluation.

    WHY PERSONA PROMPT HERE?
    The evaluator's tone matches the interviewer's persona.
    If persona is "supportive" → feedback is encouraging.
    If persona is "challenger" → feedback is rigorous.
    This creates a consistent interview experience.

    Args:
        question: The interview question that was asked
        answer: The candidate's answer
        question_category: technical/behavioral
        question_difficulty: easy/medium/hard/expert
        job_title: Role being interviewed for
        persona_prompt: Current interviewer persona system prompt
        resume_context: Brief resume summary for context

    Returns:
        Dict with all scores and feedback
    """

    prompt = f"""
You are evaluating a mock interview answer.

{persona_prompt}

Context:
- Role: {job_title}
- Question Type: {question_category}
- Difficulty: {question_difficulty}
- Candidate Background: {resume_context[:300]}

Question Asked:
{question}

Candidate's Answer:
{answer}

RESPOND ONLY WITH VALID JSON. No explanations, no markdown, no backticks.

Evaluate the answer on these 4 dimensions (each 0-10):

{{
    "overall_score": 7.5,
    "relevance_score": 8.0,
    "clarity_score": 7.0,
    "confidence_score": 6.5,
    "technical_score": 8.0,
    "strengths": [
        "specific strength 1",
        "specific strength 2"
    ],
    "weaknesses": [
        "specific weakness 1",
        "specific weakness 2"
    ],
    "ideal_answer": "A complete model answer that would score 10/10",
    "coaching_tip": "One specific actionable tip to improve this answer",
    "follow_up_question": "A natural follow-up question based on their answer"
}}

Scoring Guide:
- relevance_score:  Did they actually answer what was asked? (0=irrelevant, 10=perfectly on point)
- clarity_score:    Was it easy to understand? Clear structure? (0=confusing, 10=crystal clear)
- confidence_score: Did they sound sure of themselves? (0=very hesitant, 10=highly confident)
- technical_score:  Was the technical content accurate? (0=wrong, 10=expert-level correct)
                    For behavioral questions: was the STAR method used effectively?

Overall_score = weighted average (technical 35%, relevance 30%, clarity 20%, confidence 15%)

Be specific in strengths/weaknesses — reference actual things they said.
ideal_answer should be 3-5 sentences showing a perfect response.
coaching_tip should be ONE actionable improvement they can apply immediately.

Difficulty context for {question_difficulty}:
- easy:   basic understanding expected, penalize heavily for wrong fundamentals
- medium: practical application expected, reward specific examples
- hard:   deep knowledge expected, reward trade-off awareness
- expert: architectural thinking expected, reward nuanced judgment
"""

    try:
        response = await openai_client.chat.completions.create(
            model=settings.AZURE_OPENAI_MINI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.MAX_TOKENS_MINI,
            temperature=0.3,  # Low but not zero — some variation in feedback is good
        )

        response_text = response.choices[0].message.content.strip()
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        evaluation = json.loads(response_text)
        logger.info(
            f"Evaluation complete: overall={evaluation.get('overall_score')}"
        )
        return evaluation

    except json.JSONDecodeError as e:
        logger.error(f"GPT returned invalid JSON for evaluation: {e}")
        return _fallback_evaluation(answer)
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise


# ============================================
# FUNCTION 2: Fallback Evaluation
# ============================================
def _fallback_evaluation(answer: str) -> dict:
    """
    Basic evaluation if GPT fails.
    Better than crashing — gives user something.
    """
    word_count = len(answer.split())
    base_score = min(word_count / 10, 7.0)  # Rough score based on length

    return {
        "overall_score": round(base_score, 1),
        "relevance_score": round(base_score, 1),
        "clarity_score": round(base_score, 1),
        "confidence_score": round(base_score, 1),
        "technical_score": round(base_score, 1),
        "strengths": ["Answer was provided"],
        "weaknesses": ["Could not fully evaluate — please try again"],
        "ideal_answer": "A detailed evaluation could not be generated at this time.",
        "coaching_tip": "Try to structure your answer with: situation, approach, result.",
        "follow_up_question": "Can you elaborate on your answer?",
    }


# ============================================
# FUNCTION 3: Calculate Category Scores
# ============================================
def calculate_category_scores(responses: list[Response]) -> dict:
    """
    Calculate average scores per category from all responses.

    Used to:
    1. Update InterviewSession.category_scores
    2. Later update WeaknessSummary

    Args:
        responses: List of Response objects with scores

    Returns:
        Dict with category averages
    """
    answered = [r for r in responses if r.overall_score is not None]

    if not answered:
        return {}

    def avg(scores):
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    return {
        "overall": avg([r.overall_score for r in answered]),
        "technical": avg([r.technical_score for r in answered]),
        "clarity": avg([r.clarity_score for r in answered]),
        "confidence": avg([r.confidence_score for r in answered]),
        "relevance": avg([r.relevance_score for r in answered]),
        "communication": avg([
            ((r.clarity_score or 0) + (r.confidence_score or 0)) / 2
            for r in answered
        ]),
    }


# ============================================
# FUNCTION 4: Submit Answer (Main Function)
# ============================================
async def submit_answer(
    db: AsyncSession,
    session_id: UUID,
    user: User,
    question_number: int,
    answer_text: str,
    is_audio: bool = False,
    stress_score: Optional[float] = None,
    stress_signals: Optional[dict] = None,
    latency_ms: int = 0,
) -> dict:
    """
    Process a submitted answer end-to-end.

    Steps:
    1. Find the Response row for this question
    2. Get session context (job title, persona)
    3. Compute stress if not already done (text answers)
    4. Evaluate with GPT
    5. Save all scores to Response row
    6. Check if session is complete
    7. Update session scores if complete
    8. Return evaluation results

    Args:
        db: Database session
        session_id: Current interview session ID
        user: Current user
        question_number: Which question is being answered (1-based)
        answer_text: The answer text (typed or transcribed)
        is_audio: Was this an audio answer?
        stress_score: Pre-computed stress score (from audio)
        stress_signals: Pre-computed stress signals (from audio)
        latency_ms: Response latency

    Returns:
        Dict with evaluation results + next question info
    """

    # ---- Step 1: Get Session ----
    session_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user.id,
        )
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise ValueError("Interview session not found.")

    if session.status == SessionStatus.COMPLETED:
        raise ValueError("This interview session is already completed.")

    # ---- Step 2: Get Response Row ----
    response_result = await db.execute(
        select(Response).where(
            Response.session_id == session_id,
            Response.question_number == question_number,
        )
    )
    response = response_result.scalar_one_or_none()

    if not response:
        raise ValueError(f"Question {question_number} not found in this session.")

    if response.answer_text:
        raise ValueError(f"Question {question_number} has already been answered.")

    # ---- Step 3: Compute Stress For Text Answers ----
    # Audio answers already have stress computed in audio_service
    # Text answers need stress computed here
    if not is_audio:
        stress_result = compute_stress_score(
            text=answer_text,
            latency_ms=latency_ms,
            question_category=response.question_category or "technical",
        )
        stress_score = stress_result["stress_score"]
        stress_signals = stress_result["signals"]
        persona = stress_result["persona"]
    else:
        # Use pre-computed persona from audio stress
        from services.stress_service import select_persona
        persona = select_persona(stress_score or 5.0)

    # ---- Step 4: Get Persona Prompt ----
    persona_prompt = get_persona_prompt(persona)

    # ---- Step 5: Evaluate With GPT ----
    logger.info(
        f"Evaluating Q{question_number} | "
        f"persona={persona} | "
        f"stress={stress_score}"
    )

    # Get resume context for better evaluation
    from db.models.resume import Resume
    resume_result = await db.execute(
        select(Resume).where(Resume.id == session.resume_id)
    )
    resume = resume_result.scalar_one_or_none()
    resume_context = resume.raw_text[:300] if resume else ""

    evaluation = await evaluate_answer_with_gpt(
        question=response.question_text,
        answer=answer_text,
        question_category=response.question_category or "technical",
        question_difficulty=response.question_difficulty or "medium",
        job_title=session.job_title or user.target_role or "Software Engineer",
        persona_prompt=persona_prompt,
        resume_context=resume_context,
    )

    # ---- Step 6: Save Everything To Response Row ----
    response.answer_text = answer_text
    response.is_audio_answer = is_audio
    response.response_latency_ms = latency_ms
    response.stress_score = stress_score
    response.stress_signals = stress_signals
    response.interviewer_persona = persona

    # Scores
    response.overall_score = evaluation.get("overall_score")
    response.relevance_score = evaluation.get("relevance_score")
    response.clarity_score = evaluation.get("clarity_score")
    response.confidence_score = evaluation.get("confidence_score")
    response.technical_score = evaluation.get("technical_score")

    # Feedback
    response.strengths = evaluation.get("strengths", [])
    response.weaknesses = evaluation.get("weaknesses", [])
    response.ideal_answer = evaluation.get("ideal_answer", "")
    response.coaching_tip = evaluation.get("coaching_tip", "")

    # ---- Step 7: Check If Session Complete ----
    # Count answered questions
    all_responses_result = await db.execute(
        select(Response).where(Response.session_id == session_id)
    )
    all_responses = all_responses_result.scalars().all()

    # Count including current answer (already set above)
    answered_count = sum(1 for r in all_responses if r.answer_text is not None)
    session.current_question_index = min(answered_count, session.total_questions - 1)

    is_session_complete = answered_count >= session.total_questions

    # ---- Step 8: Update Session If Complete ----
    if is_session_complete:
        session.status = SessionStatus.COMPLETED.value
        category_scores = calculate_category_scores(all_responses)
        session.overall_score = category_scores.get("overall")
        session.category_scores = category_scores

        # Average stress across all responses
        stress_scores = [r.stress_score for r in all_responses if r.stress_score]
        if stress_scores:
            session.avg_stress_score = round(
                sum(stress_scores) / len(stress_scores), 2
            )

        logger.info(
            f"Session {session_id} COMPLETED | "
            f"overall={session.overall_score}"
        )

    await db.flush()

    # ---- Step 9: Build Response ----
    return {
        # Evaluation results
        "question_number": question_number,
        "overall_score": evaluation.get("overall_score"),
        "relevance_score": evaluation.get("relevance_score"),
        "clarity_score": evaluation.get("clarity_score"),
        "confidence_score": evaluation.get("confidence_score"),
        "technical_score": evaluation.get("technical_score"),
        "scores": {
            "relevance": evaluation.get("relevance_score"),
            "clarity": evaluation.get("clarity_score"),
            "confidence": evaluation.get("confidence_score"),
            "technical": evaluation.get("technical_score"),
        },
        "strengths": evaluation.get("strengths", []),
        "weaknesses": evaluation.get("weaknesses", []),
        "ideal_answer": evaluation.get("ideal_answer", ""),
        "coaching_tip": evaluation.get("coaching_tip", ""),
        "follow_up_question": evaluation.get("follow_up_question", ""),

        # Stress info
        "stress_score": stress_score,
        "interviewer_persona": persona,
        "persona": persona,

        # Session progress
        "session_complete": is_session_complete,
        "questions_answered": answered_count,
        "total_questions": session.total_questions,
        "current_question_index": session.current_question_index,
        "session_overall_score": session.overall_score if is_session_complete else None,
    }


# ============================================
# HOOK: Trigger Memory Update After Session
# ============================================
# Called at the bottom of submit_answer()
# when session is marked COMPLETED.
# Added in Step 8.
async def trigger_memory_update(
    db: AsyncSession,
    session_id: UUID,
    user: User,
) -> None:
    """
    Trigger memory update after session completes.
    Runs after submit_answer detects session is done.
    Wrapped in try/except so memory failure never
    blocks the user from seeing their evaluation.
    """
    try:
        from services.memory_service import update_memory_after_session
        await update_memory_after_session(db, session_id, user)
        logger.info(f"Memory updated for session {session_id}")
    except Exception as e:
        logger.error(f"Memory update failed (non-critical): {e}")
