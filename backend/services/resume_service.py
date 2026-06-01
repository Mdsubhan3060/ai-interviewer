# ============================================
# services/resume_service.py
# ============================================
# WHY THIS FILE EXISTS:
# All the BRAIN work for resumes lives here.
# The API file (resume.py) just receives requests.
# This file actually DOES the work:
#   - Extract text from PDF
#   - Parse skills/experience/education using GPT
#   - Generate HuggingFace embedding
#   - Save everything to PostgreSQL
#
# WHY SEPARATE FROM API?
# Clean separation of concerns:
#   api/resume.py       = "receive request, send response"
#   services/resume.py  = "do the actual work"
#
# This means you can call resume_service from:
#   - The API endpoint
#   - A background task
#   - A test
#   - Another service
# Without duplicating code.
# ============================================

import io
import json
import logging
import re
from typing import Optional
from uuid import UUID, uuid4

import numpy as np
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncAzureOpenAI
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient, ContentSettings
from fastapi.concurrency import run_in_threadpool

from core.config import settings
from db.models.resume import Resume
from db.models.user import User

logger = logging.getLogger(__name__)

# ============================================
# Azure OpenAI Client
# ============================================
# We use GPT only for the PARSING step
# (extracting skills/experience/education from raw text).
# Embeddings use HuggingFace (free, local).
# ============================================
openai_client = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_API_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version=settings.AZURE_OPENAI_API_VERSION,
)


def _upload_resume_to_blob_sync(
    user_id: UUID,
    filename: str,
    file_bytes: bytes,
) -> str:
    """Upload the original PDF to Azure Blob Storage and return its URL."""
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        raise ValueError("Azure Storage connection string is not configured.")

    safe_filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    blob_name = f"resumes/{user_id}/{uuid4()}-{safe_filename or 'resume.pdf'}"

    service_client = BlobServiceClient.from_connection_string(
        settings.AZURE_STORAGE_CONNECTION_STRING
    )
    container_client = service_client.get_container_client(
        settings.AZURE_STORAGE_CONTAINER_NAME
    )

    try:
        container_client.create_container()
    except ResourceExistsError:
        pass

    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(
        file_bytes,
        overwrite=False,
        content_settings=ContentSettings(content_type="application/pdf"),
    )
    return blob_client.url


async def upload_resume_to_blob(
    user_id: UUID,
    filename: str,
    file_bytes: bytes,
) -> str:
    """Async wrapper for Azure Blob upload."""
    return await run_in_threadpool(
        _upload_resume_to_blob_sync,
        user_id,
        filename,
        file_bytes,
    )


# ============================================
# FUNCTION 1: Extract Text From PDF
# ============================================
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Takes raw PDF bytes and returns extracted text string.

    PyPDF reads each page and extracts all text.
    It handles most standard PDF formats but may struggle
    with scanned PDFs (images) - those need OCR (future feature).

    Args:
        file_bytes: Raw bytes of the uploaded PDF file

    Returns:
        Extracted text as a single string
    """
    try:
        # io.BytesIO wraps bytes in a file-like object
        # PyPDF needs something it can "read" like a file
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)

        # Extract text from each page and join
        pages_text = []
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)
            logger.debug(f"Page {page_num + 1}: extracted {len(page_text or '')} chars")

        full_text = "\n".join(pages_text)

        if not full_text.strip():
            raise ValueError(
                "No text could be extracted. "
                "This might be a scanned PDF (image-based). "
                "Please upload a text-based PDF."
            )

        logger.info(f"Extracted {len(full_text)} characters from PDF")
        return full_text

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ValueError(f"Could not read PDF: {str(e)}")


# ============================================
# FUNCTION 2: Parse Experience String → Months
# ============================================
def parse_experience(exp_str: str) -> int:
    """
    Convert experience string to total months.

    Examples:
        "fresher"        → 0
        "0-6 months"     → 3
        "2 years"        → 24
        "3-5 years"      → 48
        "5+ years"       → 60

    Args:
        exp_str: Experience string from resume or user input

    Returns:
        Total months as integer
    """
    if not exp_str:
        return 0

    exp_str = exp_str.lower().strip()

    # Months
    if "month" in exp_str:
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", exp_str)]
        if len(nums) >= 2:
            return int((nums[0] + nums[1]) / 2)
        if len(nums) == 1:
            return int(nums[0])
        try:
            return int(float(exp_str.replace("+", "").strip()))
        except ValueError:
            return 0

    # Years
    if "year" in exp_str:
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", exp_str)]
        if len(nums) >= 2:
            return int(((nums[0] + nums[1]) / 2) * 12)
        if len(nums) == 1:
            return int(nums[0] * 12)
        try:
            return int(float(exp_str.replace("+", "").strip()) * 12)
        except ValueError:
            return 0

    # Fresher / no experience / internship without numeric duration
    # Keep this after numeric parsing so strings like
    # "0-6 months internship" correctly return 3.
    if any(word in exp_str for word in ["fresher", "no experience", "student", "intern"]):
        return 0

    return 0  # fallback


# ============================================
# FUNCTION 3: Parse Resume With GPT
# ============================================
async def parse_resume_with_gpt(raw_text: str) -> dict:
    """
    Send resume text to GPT and get structured data back.

    GPT reads the raw text and extracts:
    - Skills (Python, React, SQL, etc.)
    - Work experience (company, role, duration, description)
    - Education (degree, university, year)
    - Total experience summary

    We use gpt-4o-mini here (cheaper) because this is
    extraction work, not creative generation.
    GPT-4 saved for cover letters and question generation.

    Args:
        raw_text: Full text extracted from PDF

    Returns:
        Dict with skills, experience, education, summary
    """

    # ---- The Prompt ----
    # We tell GPT EXACTLY what format to return.
    # "respond only in JSON" = no extra text, no markdown
    # This makes parsing the response reliable.
    prompt = f"""
You are a resume parser. Extract structured information from this resume.

RESPOND ONLY WITH VALID JSON. No explanations, no markdown, no backticks.

Extract these fields:
{{
    "skills": ["skill1", "skill2", ...],
    "experience": [
        {{
            "company": "company name",
            "role": "job title",
            "duration": "e.g. 2 years 3 months",
            "duration_months": 27,
            "description": "brief summary of responsibilities",
            "is_current": true/false
        }}
    ],
    "education": [
        {{
            "degree": "e.g. B.Tech Computer Science",
            "institution": "university/college name",
            "year": "graduation year or expected year",
            "grade": "GPA or percentage if mentioned"
        }}
    ],
    "total_experience_months": 0,
    "experience_label": "e.g. Fresher / 2 years / 5+ years",
    "summary": "2-3 sentence professional summary based on the resume"
}}

RESUME TEXT:
{raw_text[:4000]}
"""
    # Note: We limit to 4000 chars to control token cost.
    # Most resumes are 1-2 pages = well within this limit.

    try:
        response = await openai_client.chat.completions.create(
            model=settings.AZURE_OPENAI_MINI_DEPLOYMENT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.MAX_TOKENS_MINI,
            temperature=0,  # 0 = deterministic, no creativity needed here
        )

        response_text = response.choices[0].message.content.strip()

        # ---- Parse JSON Response ----
        # Sometimes GPT adds ```json ... ``` despite instructions
        # Strip those just in case
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(response_text)
        logger.info(f"GPT parsed {len(parsed.get('skills', []))} skills")
        return parsed

    except json.JSONDecodeError as e:
        logger.error(f"GPT returned invalid JSON: {e}")
        # Return empty structure rather than crashing
        return {
            "skills": [],
            "experience": [],
            "education": [],
            "total_experience_months": 0,
            "experience_label": "Unknown",
            "summary": "",
        }
    except Exception as e:
        logger.error(f"GPT parsing failed: {e}")
        raise


# ============================================
# FUNCTION 4: Generate Azure OpenAI Embedding
# ============================================
async def generate_embedding(text: str) -> list[float]:
    """Generate an embedding with Azure OpenAI instead of loading local ML models."""
    response = await openai_client.embeddings.create(
        model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        input=text[:8000],
    )
    return response.data[0].embedding


# ============================================
# FUNCTION 5: Save Resume To Database
# ============================================
async def save_resume(
    db: AsyncSession,
    user: User,
    filename: str,
    file_bytes: bytes,
) -> Resume:
    """
    Main function that orchestrates the entire resume processing pipeline.

    Steps:
    1. Extract text from PDF
    2. Parse with GPT (skills, experience, education)
    3. Generate embedding for job matching
    4. Deactivate old resumes (only one active at a time)
    5. Save new resume to database

    Args:
        db: Database session
        user: Current logged in user
        filename: Original filename of uploaded PDF
        file_bytes: Raw bytes of the PDF

    Returns:
        The saved Resume database object
    """

    # ---- Step 1: Store Original PDF ----
    logger.info(f"Processing resume: {filename} for user {user.id}")
    blob_url = await upload_resume_to_blob(user.id, filename, file_bytes)
    logger.info("Resume PDF uploaded to Azure Blob Storage")

    # ---- Step 2: Extract PDF Text ----
    raw_text = extract_text_from_pdf(file_bytes)

    # ---- Step 3: Parse With GPT ----
    logger.info("Parsing resume with GPT...")
    parsed_data = await parse_resume_with_gpt(raw_text)

    # ---- Step 4: Generate Embedding ----
    logger.info("Generating Azure OpenAI embedding...")
    # We embed skills + experience summary for best matching results
    skills_text = " ".join(parsed_data.get("skills", []))
    embed_text = f"{skills_text} {parsed_data.get('summary', '')} {raw_text[:500]}"
    embedding = await generate_embedding(embed_text)

    # ---- Step 5: Deactivate Old Resumes ----
    # We only want ONE active resume per user
    # (the most recently uploaded one)
    existing_resumes = await db.execute(
        select(Resume).where(
            Resume.user_id == user.id,
            Resume.is_active == True,
        )
    )
    for old_resume in existing_resumes.scalars().all():
        old_resume.is_active = False
        logger.info(f"Deactivated old resume: {old_resume.id}")

    # ---- Step 6: Create New Resume ----
    experience_label = parsed_data.get("experience_label", "")
    experience_months = parsed_data.get("total_experience_months", 0)

    # If GPT didn't calculate months, use our parse_experience function
    if not experience_months and experience_label:
        experience_months = parse_experience(experience_label)

    new_resume = Resume(
        user_id=user.id,
        original_filename=filename,
        blob_url=blob_url,
        raw_text=raw_text,
        skills_extracted=parsed_data.get("skills", []),
        experience_extracted=parsed_data.get("experience", []),
        education_extracted=parsed_data.get("education", []),
        embedding=embedding,
        experience_label=experience_label,
        experience_months=experience_months,
        is_active=True,
    )

    db.add(new_resume)
    await db.flush()  # Gets the ID without committing yet
    logger.info(f"✅ Resume saved: {new_resume.id}")

    return new_resume


# ============================================
# FUNCTION 6: Get User's Active Resume
# ============================================
async def get_active_resume(
    db: AsyncSession,
    user_id: UUID,
) -> Optional[Resume]:
    """
    Get the user's currently active resume.
    Returns None if user hasn't uploaded a resume yet.
    """
    result = await db.execute(
        select(Resume).where(
            Resume.user_id == user_id,
            Resume.is_active == True,
        )
    )
    return result.scalar_one_or_none()


# ============================================
# FUNCTION 7: Get All User Resumes
# ============================================
async def get_all_resumes(
    db: AsyncSession,
    user_id: UUID,
) -> list[Resume]:
    """
    Get all resumes for a user (including inactive ones).
    Used for resume history page.
    """
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
    )
    return result.scalars().all()
