# ============================================
# services/job_service.py
# ============================================
# WHY THIS FILE EXISTS:
# All job matching logic lives here.
#
# HOW JOB MATCHING WORKS:
#
# 1. EMBEDDING SIMILARITY (70% of score)
#    Convert both resume + job description to vectors.
#    Calculate cosine similarity between them.
#    Similar content = high score.
#
# 2. SKILL MATCHING (30% of score)
#    GPT compares resume skills vs job required skills.
#    Finds: matched skills, missing skills, bonus skills.
#
# FINAL SCORE = (similarity * 0.7) + (skill_match * 0.3)
# Scaled to 0-100.
#
# WHY COSINE SIMILARITY?
# It measures the ANGLE between two vectors.
# Angle = 0°  → identical meaning → score 1.0
# Angle = 90° → unrelated        → score 0.0
# We don't care about vector LENGTH, only direction.
# ============================================

import json
import logging
import numpy as np
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncAzureOpenAI

from core.config import settings
from db.models.job_match import JobMatch
from db.models.resume import Resume
from db.models.user import User
from services.resume_service import generate_embedding, get_active_resume

logger = logging.getLogger(__name__)

# Azure OpenAI client (reused from resume_service pattern)
openai_client = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version=settings.AZURE_OPENAI_API_VERSION,
)


# ============================================
# FUNCTION 1: Cosine Similarity
# ============================================
def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate how similar two embedding vectors are.

    WHAT IS COSINE SIMILARITY?
    Imagine two arrows pointing in space.
    If they point in the SAME direction → similarity = 1.0 (identical)
    If they point at 90° to each other → similarity = 0.0 (unrelated)
    If they point OPPOSITE directions  → similarity = -1.0 (opposite meaning)

    For resumes vs job descriptions:
    0.85+ = very strong match
    0.70  = good match
    0.50  = weak match
    <0.40 = poor match

    Args:
        vec1: Resume embedding (384 floats)
        vec2: Job description embedding (384 floats)

    Returns:
        Float between 0 and 1
    """
    # Convert to numpy arrays for math operations
    a = np.array(vec1)
    b = np.array(vec2)

    # Cosine similarity formula:
    # (a · b) / (||a|| × ||b||)
    # dot product divided by product of magnitudes
    dot_product = np.dot(a, b)
    magnitude_a = np.linalg.norm(a)
    magnitude_b = np.linalg.norm(b)

    # Avoid division by zero
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    similarity = dot_product / (magnitude_a * magnitude_b)

    # Clip to [0, 1] range (similarity is never negative for text)
    return float(np.clip(similarity, 0, 1))


# ============================================
# FUNCTION 2: Analyze Skills With GPT
# ============================================
async def analyze_skills_with_gpt(
    resume_skills: list[str],
    resume_text: str,
    job_description: str,
) -> dict:
    """
    Use GPT to compare resume skills against job requirements.

    WHY GPT FOR SKILLS?
    Simple string matching fails:
      Resume has: "ML"
      Job needs:  "Machine Learning"
      String match: ❌ MISS
      GPT:         ✅ MATCH (understands they're the same)

    GPT understands:
      - Abbreviations (ML = Machine Learning)
      - Synonyms (ReactJS = React)
      - Related skills (knows Django if you know Flask)

    Args:
        resume_skills: Skills extracted from resume
        resume_text: Full resume text (for context)
        job_description: The job posting text

    Returns:
        Dict with matched_skills, missing_skills, bonus_skills, skill_score
    """

    prompt = f"""
You are a technical recruiter analyzing a candidate's resume against a job description.

RESPOND ONLY WITH VALID JSON. No explanations, no markdown.

Resume Skills: {json.dumps(resume_skills)}

Job Description:
{job_description[:3000]}

Resume Summary (for context):
{resume_text[:1000]}

Analyze and return:
{{
    "matched_skills": ["skills from resume that match job requirements"],
    "missing_skills": ["skills job requires that resume doesn't have"],
    "bonus_skills": ["skills resume has beyond what job requires"],
    "skill_match_score": 75,
    "experience_match": 80,
    "education_match": 70,
    "match_summary": "2-3 sentence summary of how well candidate fits",
    "top_recommendation": "single most important thing candidate should add/improve"
}}

Rules:
- skill_match_score: 0-100 based on % of required skills matched
- experience_match: 0-100 based on experience level fit
- education_match: 0-100 based on education requirements
- Be specific about missing skills (name exact technologies)
- matched_skills should use the job's terminology, not resume's
"""

    try:
        response = await openai_client.chat.completions.create(
            model=settings.AZURE_OPENAI_MINI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.MAX_TOKENS_MINI,
            temperature=0,
        )

        response_text = response.choices[0].message.content.strip()
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        return json.loads(response_text)

    except json.JSONDecodeError:
        logger.error("GPT returned invalid JSON for skill analysis")
        return {
            "matched_skills": [],
            "missing_skills": [],
            "bonus_skills": [],
            "skill_match_score": 0,
            "experience_match": 0,
            "education_match": 0,
            "match_summary": "Could not analyze skills.",
            "top_recommendation": "",
        }
    except Exception as e:
        logger.error(f"Skill analysis failed: {e}")
        raise


# ============================================
# FUNCTION 3: Calculate Final Match Score
# ============================================
def calculate_final_score(
    similarity_score: float,
    skill_match_score: float,
    experience_match: float,
    education_match: float,
) -> float:
    """
    Combine all signals into one final 0-100 score.

    WEIGHTS (must add to 1.0):
    - Embedding similarity: 40% (overall content match)
    - Skill match:          35% (most important for recruiters)
    - Experience match:     15% (years of experience fit)
    - Education match:      10% (degree requirements)

    Args:
        similarity_score: Cosine similarity 0-1
        skill_match_score: GPT skill score 0-100
        experience_match: GPT experience score 0-100
        education_match: GPT education score 0-100

    Returns:
        Final score 0-100
    """
    # Convert similarity from 0-1 to 0-100
    similarity_100 = similarity_score * 100

    final = (
        similarity_100  * 0.40 +
        skill_match_score * 0.35 +
        experience_match  * 0.15 +
        education_match   * 0.10
    )

    # Round to 1 decimal place
    return round(final, 1)


# ============================================
# FUNCTION 4: Match Job (Main Function)
# ============================================
async def match_job(
    db: AsyncSession,
    user: User,
    job_description: str,
    job_title: Optional[str] = None,
    company_name: Optional[str] = None,
) -> JobMatch:
    """
    Full job matching pipeline.

    Steps:
    1. Get user's active resume
    2. Embed job description with HuggingFace
    3. Calculate cosine similarity with resume embedding
    4. Analyze skills with GPT
    5. Calculate final score
    6. Save result to database
    7. Return JobMatch object

    Args:
        db: Database session
        user: Current logged in user
        job_description: Full job posting text
        job_title: Optional job title
        company_name: Optional company name

    Returns:
        Saved JobMatch object
    """

    # ---- Step 1: Get Active Resume ----
    resume = await get_active_resume(db, user.id)
    if not resume:
        raise ValueError(
            "No resume found. Please upload your resume before matching jobs."
        )

    if not resume.embedding:
        raise ValueError(
            "Resume embedding not found. Please re-upload your resume."
        )

    logger.info(f"Matching job for user {user.id}: {job_title or 'Untitled'}")

    # ---- Step 2: Embed Job Description ----
    logger.info("Generating job description embedding...")
    job_embedding = generate_embedding(job_description[:2000])

    # ---- Step 3: Cosine Similarity ----
    similarity = cosine_similarity(resume.embedding, job_embedding)
    logger.info(f"Cosine similarity: {similarity:.3f}")

    # ---- Step 4: GPT Skill Analysis ----
    logger.info("Analyzing skills with GPT...")
    skill_analysis = await analyze_skills_with_gpt(
        resume_skills=resume.skills_extracted or [],
        resume_text=resume.raw_text,
        job_description=job_description,
    )

    # ---- Step 5: Final Score ----
    final_score = calculate_final_score(
        similarity_score=similarity,
        skill_match_score=skill_analysis.get("skill_match_score", 0),
        experience_match=skill_analysis.get("experience_match", 0),
        education_match=skill_analysis.get("education_match", 0),
    )
    logger.info(f"Final match score: {final_score}")

    # ---- Step 6: Save To Database ----
    job_match = JobMatch(
        user_id=user.id,
        resume_id=resume.id,
        job_title=job_title,
        company_name=company_name,
        job_description=job_description,
        match_score=final_score,
        matched_skills=skill_analysis.get("matched_skills", []),
        missing_skills=skill_analysis.get("missing_skills", []),
        bonus_skills=skill_analysis.get("bonus_skills", []),
        experience_match=skill_analysis.get("experience_match"),
        education_match=skill_analysis.get("education_match"),
        match_summary=skill_analysis.get("match_summary", ""),
    )

    db.add(job_match)
    await db.flush()
    logger.info(f"✅ Job match saved: {job_match.id}")

    return job_match


# ============================================
# FUNCTION 5: Get Match History
# ============================================
async def get_match_history(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 10,
) -> list[JobMatch]:
    """Get user's recent job matches."""
    result = await db.execute(
        select(JobMatch)
        .where(JobMatch.user_id == user_id)
        .order_by(JobMatch.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
