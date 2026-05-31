# ============================================
# api/resume.py
# ============================================
# WHY THIS FILE EXISTS:
# Defines the HTTP endpoints for resume operations.
# This file is THIN — it just:
#   1. Receives the request
#   2. Validates the input
#   3. Calls the service (which does real work)
#   4. Returns the response
#
# ALL business logic stays in services/resume_service.py
# This file only handles HTTP concerns.
# ============================================

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging
from uuid import UUID

from core.dependencies import get_current_user
from db.session import get_db
from db.models.user import User
from services.resume_service import (
    save_resume,
    get_active_resume,
    get_all_resumes,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# Response Schemas (Pydantic)
# ============================================
# WHY PYDANTIC SCHEMAS?
# When FastAPI returns data, it needs to know:
#   - What fields to include
#   - What types they are
#   - Whether they're optional
#
# These schemas define the SHAPE of our API responses.
# They also auto-generate the API docs at /docs.
#
# Think of them as contracts:
# "This endpoint will ALWAYS return these fields"
# ============================================

class ExperienceItem(BaseModel):
    company: str
    role: str
    duration: str
    duration_months: int
    description: str
    is_current: bool = False

class EducationItem(BaseModel):
    degree: str
    institution: str
    year: str
    grade: Optional[str] = None

class ResumeResponse(BaseModel):
    id: UUID
    original_filename: str
    skills_extracted: list[str]
    experience_extracted: list[dict]
    education_extracted: list[dict]
    experience_label: Optional[str]
    experience_months: Optional[int]
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True  # Allows converting SQLAlchemy model to this schema


# ============================================
# ENDPOINT 1: Upload Resume
# POST /api/v1/resume/upload
# ============================================
@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),           # The PDF file
    db: AsyncSession = Depends(get_db),     # DB session (auto-injected)
    current_user: User = Depends(get_current_user),  # Auth (auto-injected)
):
    """
    Upload and parse a resume PDF.

    What happens:
    1. Validate file is a PDF and not too large
    2. Read file bytes
    3. Call resume_service to extract, parse, embed, save
    4. Return parsed resume data

    Protected: requires valid JWT token in Authorization header
    """

    # ---- Validate File Type ----
    # We only accept PDFs
    # content_type comes from the browser when uploading
    if file.content_type not in ["application/pdf", "application/octet-stream"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    # Also check file extension as backup
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have .pdf extension.",
        )

    # ---- Validate File Size ----
    # Max 10MB for resumes (most are <1MB, 10MB is generous)
    # We read into memory, so we need to check size
    file_bytes = await file.read()

    max_size = 10 * 1024 * 1024  # 10MB in bytes
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is 10MB. Your file is {len(file_bytes) / 1024 / 1024:.1f}MB",
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ---- Process Resume ----
    try:
        resume = await save_resume(
            db=db,
            user=current_user,
            filename=file.filename,
            file_bytes=file_bytes,
        )

        # ---- Return Success Response ----
        return {
            "message": "Resume uploaded and parsed successfully",
            "resume": {
                "id": str(resume.id),
                "filename": resume.original_filename,
                "blob_url": resume.blob_url,
                "skills": resume.skills_extracted,
                "experience": resume.experience_extracted,
                "education": resume.education_extracted,
                "experience_label": resume.experience_label,
                "experience_months": resume.experience_months,
                "skills_count": len(resume.skills_extracted or []),
                "is_active": resume.is_active,
            }
        }

    except ValueError as e:
        # ValueError = our own validation errors (e.g., scanned PDF)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Resume upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process resume. Please try again.",
        )


# ============================================
# ENDPOINT 2: Get Active Resume
# GET /api/v1/resume/active
# ============================================
@router.get("/active")
async def get_my_resume(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's active resume.
    Returns 404 if user hasn't uploaded a resume yet.
    """
    resume = await get_active_resume(db, current_user.id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resume found. Please upload your resume first.",
        )

    return {
        "id": str(resume.id),
        "filename": resume.original_filename,
        "blob_url": resume.blob_url,
        "skills": resume.skills_extracted,
        "experience": resume.experience_extracted,
        "education": resume.education_extracted,
        "experience_label": resume.experience_label,
        "experience_months": resume.experience_months,
        "is_active": resume.is_active,
        "uploaded_at": resume.created_at.isoformat(),
    }


# ============================================
# ENDPOINT 3: Get All Resumes (History)
# GET /api/v1/resume/all
# ============================================
@router.get("/all")
async def get_resume_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all resumes uploaded by the current user.
    Includes inactive (old) resumes for history.
    """
    resumes = await get_all_resumes(db, current_user.id)

    return {
        "total": len(resumes),
        "resumes": [
            {
                "id": str(r.id),
                "filename": r.original_filename,
                "skills_count": len(r.skills_extracted or []),
                "experience_label": r.experience_label,
                "is_active": r.is_active,
                "uploaded_at": r.created_at.isoformat(),
            }
            for r in resumes
        ]
    }


# ============================================
# ENDPOINT 4: Delete Resume
# DELETE /api/v1/resume/{resume_id}
# ============================================
@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a specific resume.
    Users can only delete their OWN resumes.
    """
    from sqlalchemy import select, delete
    from db.models.resume import Resume

    # ---- Find Resume ----
    result = await db.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id,  # SECURITY: must own this resume
        )
    )
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found or you don't have permission to delete it.",
        )

    await db.delete(resume)

    return {"message": "Resume deleted successfully"}
