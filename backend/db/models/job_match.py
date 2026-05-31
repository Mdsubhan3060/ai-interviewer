# ============================================
# db/models/job_match.py
# ============================================
# WHY THIS FILE EXISTS:
# Every time a user runs a job match, we store the result.
# This lets us:
#   1. Show match history ("you matched 73% with Google last week")
#   2. Pre-fill interview questions with the job context
#   3. Generate cover letters without re-running the match
#   4. Track which jobs they're applying for
# ============================================

from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import BaseModel


class JobMatch(BaseModel):
    __tablename__ = "job_matches"

    # ---- Foreign Keys ----
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resume_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ---- Job Info ----
    job_title = Column(String(255), nullable=True)
    company_name = Column(String(255), nullable=True)

    # The full job description text (pasted by user)
    job_description = Column(Text, nullable=False)

    # ---- Match Results ----
    # Overall match score 0-100
    match_score = Column(Float, nullable=False)

    # Skills the user HAS that match the job
    # Example: ["Python", "FastAPI", "PostgreSQL"]
    matched_skills = Column(JSON, nullable=True, default=list)

    # Skills the job requires that user DOESN'T have
    # Example: ["Kubernetes", "Terraform", "Go"]
    missing_skills = Column(JSON, nullable=True, default=list)

    # Skills user has but job doesn't mention (bonus skills)
    # Example: ["React", "Docker"]
    bonus_skills = Column(JSON, nullable=True, default=list)

    # How well does experience level match? (0-100)
    experience_match = Column(Float, nullable=True)

    # How well does education match? (0-100)
    education_match = Column(Float, nullable=True)

    # Summary explanation of the match
    # Example: "Strong Python match but missing cloud infrastructure skills"
    match_summary = Column(Text, nullable=True)

    # ---- Cover Letter ----
    # Generated cover letter (if user requested one)
    cover_letter = Column(Text, nullable=True)

    # ---- Relationship ----
    user = relationship("User")
    resume = relationship("Resume")

    def __repr__(self):
        return f"<JobMatch {self.job_title} at {self.company_name} | score={self.match_score}>"
