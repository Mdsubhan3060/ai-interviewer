import json
import logging
from uuid import UUID

from openai import AsyncAzureOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models.interview_session import InterviewSession, InterviewType, SessionStatus
from db.models.response import Response
from db.models.resume import Resume
from db.models.user import User
from services.resume_service import get_active_resume

logger = logging.getLogger(__name__)

openai_client = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version=settings.AZURE_OPENAI_API_VERSION,
)


def _normalize_interview_type(value: str | None) -> str:
    allowed = {item.value for item in InterviewType}
    if value in allowed:
        return value
    return InterviewType.MIXED.value


def _question_to_dict(response: Response) -> dict:
    return {
        "number": response.question_number,
        "question_text": response.question_text,
        "category": response.question_category or "technical",
        "difficulty": response.question_difficulty or "medium",
    }


def _fallback_questions(job_title: str, interview_type: str, total_questions: int) -> list[dict]:
    technical = [
        f"Explain a recent technical project you built for a {job_title} role. What trade-offs did you make?",
        f"What core skills are most important for a {job_title}, and how have you used them in practice?",
        "Describe a difficult bug or production issue you handled. How did you diagnose and fix it?",
        "How do you design a solution when requirements are incomplete or changing?",
        "Tell me about a time you improved performance, reliability, or maintainability in a system.",
    ]
    behavioral = [
        "Tell me about a time you had to learn something quickly to complete a task.",
        "Describe a time you received critical feedback. What did you change afterward?",
        "Tell me about a conflict with a teammate or stakeholder and how you handled it.",
        "Describe a situation where you had to take ownership of an ambiguous problem.",
        "Tell me about a time you missed a goal or deadline. What did you learn?",
    ]

    if interview_type == InterviewType.TECHNICAL.value:
        pool = technical
    elif interview_type == InterviewType.BEHAVIORAL.value:
        pool = behavioral
    else:
        pool = []
        for index in range(max(len(technical), len(behavioral))):
            if index < len(technical):
                pool.append(technical[index])
            if index < len(behavioral):
                pool.append(behavioral[index])

    questions = []
    for index in range(total_questions):
        text = pool[index % len(pool)]
        category = "behavioral" if text.startswith(("Tell me", "Describe")) else "technical"
        questions.append(
            {
                "question_text": text,
                "category": category,
                "difficulty": "medium",
            }
        )
    return questions


async def _generate_questions_with_gpt(
    job_title: str,
    company_name: str | None,
    job_description: str | None,
    interview_type: str,
    total_questions: int,
    resume: Resume | None,
) -> list[dict]:
    resume_context = ""
    if resume:
        skills = ", ".join(resume.skills_extracted or [])
        resume_context = f"Skills: {skills}\nExperience: {resume.experience_label or ''}\nSummary: {(resume.raw_text or '')[:1200]}"

    prompt = f"""
You are generating mock interview questions.

Return ONLY valid JSON. No markdown, no explanation.

Role: {job_title}
Company: {company_name or "Not specified"}
Interview type: {interview_type}
Total questions: {total_questions}

Job description:
{(job_description or "")[:2500]}

Candidate resume context:
{resume_context}

Return this exact shape:
{{
  "questions": [
    {{
      "question_text": "question text",
      "category": "technical",
      "difficulty": "medium"
    }}
  ]
}}

Rules:
- Generate exactly {total_questions} questions.
- category must be "technical" or "behavioral".
- difficulty must be "easy", "medium", or "hard".
- For mixed interviews, include both technical and behavioral questions.
- Make questions specific to the role and job description when available.
"""

    response = await openai_client.chat.completions.create(
        model=settings.AZURE_OPENAI_GPT4_DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=settings.MAX_TOKENS_GPT4,
        temperature=0.5,
    )
    text = response.choices[0].message.content.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    data = json.loads(text)
    questions = data.get("questions", [])
    if not isinstance(questions, list) or len(questions) < total_questions:
        raise ValueError("Question generator returned an invalid question list.")
    return questions[:total_questions]


async def start_interview_session(
    db: AsyncSession,
    user: User,
    job_description: str | None = None,
    job_title: str | None = None,
    company_name: str | None = None,
    interview_type: str = InterviewType.MIXED.value,
    total_questions: int = 5,
) -> dict:
    job_title = (job_title or user.target_role or "Software Engineer").strip()
    interview_type = _normalize_interview_type(interview_type)
    total_questions = max(1, min(20, int(total_questions or 5)))

    resume = await get_active_resume(db, user.id)

    try:
        questions = await _generate_questions_with_gpt(
            job_title=job_title,
            company_name=company_name,
            job_description=job_description,
            interview_type=interview_type,
            total_questions=total_questions,
            resume=resume,
        )
    except Exception as exc:
        logger.error("Question generation failed, using fallback questions: %s", exc)
        questions = _fallback_questions(job_title, interview_type, total_questions)

    session = InterviewSession(
        user_id=user.id,
        resume_id=resume.id if resume else None,
        job_description=job_description,
        job_title=job_title,
        company_name=company_name,
        interview_type=interview_type,
        total_questions=total_questions,
        current_question_index=0,
        status=SessionStatus.IN_PROGRESS.value,
    )
    db.add(session)
    await db.flush()

    response_rows = []
    for index, question in enumerate(questions, start=1):
        response = Response(
            session_id=session.id,
            question_number=index,
            question_text=question.get("question_text") or question.get("text") or "",
            question_category=question.get("category") or "technical",
            question_difficulty=question.get("difficulty") or "medium",
            interviewer_persona="neutral",
        )
        response_rows.append(response)
        db.add(response)

    await db.flush()

    return {
        "session": {
            "id": str(session.id),
            "status": session.status,
            "job_title": session.job_title,
            "company_name": session.company_name,
            "interview_type": session.interview_type,
            "total_questions": session.total_questions,
            "current_question_index": session.current_question_index,
        },
        "first_question": _question_to_dict(response_rows[0]),
    }


async def get_next_question(
    db: AsyncSession,
    session_id: UUID,
    user_id: UUID,
) -> dict | None:
    session_result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user_id,
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise ValueError("Interview session not found.")

    if session.status in {SessionStatus.COMPLETED.value, str(SessionStatus.COMPLETED)}:
        return None

    response_result = await db.execute(
        select(Response)
        .where(
            Response.session_id == session_id,
            Response.answer_text.is_(None),
        )
        .order_by(Response.question_number)
    )
    next_response = response_result.scalars().first()
    if not next_response:
        session.status = SessionStatus.COMPLETED.value
        return None

    session.current_question_index = max(next_response.question_number - 1, 0)
    await db.flush()
    return {
        **_question_to_dict(next_response),
        "current_question_index": session.current_question_index,
        "total_questions": session.total_questions,
    }
