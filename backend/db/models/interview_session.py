# ============================================
# db/models/interview_session.py
# ============================================
# WHY THIS FILE EXISTS:
# Every time a user starts a mock interview, we create a Session.
# Think of it like a "game session" in a video game —
# it tracks everything that happened in that one sitting.
#
# ONE session = ONE complete mock interview
# ONE session has MANY responses (one per question asked)
# ============================================

from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import BaseModel
import enum


# ---- Session Status ----
# Enum = a fixed list of allowed values.
# Prevents typos like "complet" or "Completed" from sneaking into DB.
class SessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"   # User is currently being interviewed
    COMPLETED = "completed"       # User finished all questions
    ABANDONED = "abandoned"       # User left midway


# ---- Interview Type ----
class InterviewType(str, enum.Enum):
    TECHNICAL = "technical"       # Coding, system design questions
    BEHAVIORAL = "behavioral"     # Tell me about yourself, conflict resolution
    MIXED = "mixed"               # Both (default)


class InterviewSession(BaseModel):
    __tablename__ = "interview_sessions"

    # ---- Foreign Keys ----
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which resume was used for this interview?
    # (User might have multiple resumes for different roles)
    resume_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ---- Job Context ----
    # The job description the user is preparing for
    job_description = Column(Text, nullable=True)
    job_title = Column(String(255), nullable=True)        # "Senior Python Developer"
    company_name = Column(String(255), nullable=True)     # "Google"

    # ---- Session Config ----
    interview_type = Column(
        String(50),
        default=InterviewType.MIXED,
        nullable=False,
    )

    # How many questions to ask in this session (default 5)
    total_questions = Column(Integer, default=5, nullable=False)

    # Which question number are we on right now? (1-based)
    current_question_index = Column(Integer, default=0, nullable=False)

    # ---- Status ----
    status = Column(
        String(50),
        default=SessionStatus.IN_PROGRESS,
        nullable=False,
        index=True,  # Fast lookup of all "in_progress" sessions
    )

    # ---- Scores ----
    # Overall average score for this session (0-10)
    # Calculated after session completes
    overall_score = Column(Float, nullable=True)

    # Breakdown by category (calculated at end of session)
    # Example: {"technical": 7.5, "communication": 6.0, "confidence": 8.0}
    category_scores = Column(JSON, nullable=True, default=dict)

    # ---- Stress Tracking (Our Differentiator) ----
    # Average stress score across all answers in this session
    avg_stress_score = Column(Float, nullable=True)

    # Which persona was used most? (challenger/neutral/prober/supportive)
    dominant_persona = Column(String(50), nullable=True)

    # ---- Adaptive Interview Data ----
    # Areas specifically targeted in this session based on past weaknesses
    # Example: ["communication", "technical_depth"]
    targeted_weaknesses = Column(JSON, nullable=True, default=list)

    # ---- Relationships ----
    user = relationship("User", back_populates="sessions")
    responses = relationship(
        "Response",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Response.question_number",  # Always in order
    )

    def __repr__(self):
        return f"<InterviewSession {self.id} | {self.status} | score={self.overall_score}>"
