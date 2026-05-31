# ============================================
# db/models/weakness_summary.py
# ============================================
# WHY THIS FILE EXISTS:
# This is the MEMORY of the entire system.
#
# After every interview session, we update this table
# with the user's running averages across ALL sessions.
# This powers two critical features:
#
# 1. DASHBOARD: "Your average technical score is 5.2/10"
# 2. ADAPTIVE INTERVIEW: "Last time you scored low on confidence,
#    so this session will ask more confidence-building questions"
#
# ONE row per user. Always updated, never duplicated.
# ============================================

from sqlalchemy import Column, Float, Integer, JSON, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import BaseModel


class WeaknessSummary(BaseModel):
    __tablename__ = "weakness_summaries"

    # ---- Foreign Key ----
    # One-to-one with User (each user has exactly one summary)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # Enforces one-to-one at database level
        index=True,
    )

    # ---- Session Counts ----
    # How many total sessions has this user completed?
    total_sessions = Column(Integer, default=0, nullable=False)

    # How many total questions answered across all sessions?
    total_questions_answered = Column(Integer, default=0, nullable=False)

    # ---- Running Averages (updated after each session) ----
    # Overall average score across everything (0-10)
    overall_avg = Column(Float, nullable=True)

    # Communication = clarity + confidence combined
    communication_avg = Column(Float, nullable=True)

    # Technical = technical correctness score
    technical_avg = Column(Float, nullable=True)

    # Confidence = standalone confidence score
    confidence_avg = Column(Float, nullable=True)

    # Relevance = how well answers addressed the actual question
    relevance_avg = Column(Float, nullable=True)

    # ---- Stress Tracking ----
    # Average stress score across all sessions (0-10)
    avg_stress_score = Column(Float, nullable=True)

    # Is stress improving over time? (positive = getting calmer)
    stress_trend = Column(Float, nullable=True)

    # ---- Identified Weak Areas ----
    # Top 3 weakest categories right now
    # Example: ["technical_depth", "confidence", "conciseness"]
    # Used by Adaptive Interview to target these areas
    top_weaknesses = Column(JSON, nullable=True, default=list)

    # Top 3 strongest areas
    # Example: ["problem_solving", "communication", "examples"]
    top_strengths = Column(JSON, nullable=True, default=list)

    # ---- Trend Data (for dashboard charts) ----
    # Last 10 session scores in chronological order
    # Example: [5.2, 5.8, 6.1, 6.0, 7.2, 7.5, 7.1, 7.8, 8.0, 8.2]
    # Used to draw the "improvement over time" line chart
    score_history = Column(JSON, nullable=True, default=list)

    # Score broken down by category over time
    # Example: {"technical": [4.0, 5.0, 6.5], "confidence": [6.0, 7.0, 7.5]}
    category_score_history = Column(JSON, nullable=True, default=dict)

    # ---- Personalized Recommendations ----
    # AI-generated improvement suggestions based on weakness patterns
    # Example: ["Practice STAR method for behavioral questions",
    #           "Review system design fundamentals",
    #           "Work on speaking more slowly and clearly"]
    recommendations = Column(JSON, nullable=True, default=list)

    # Last time recommendations were regenerated (don't regenerate every session)
    last_recommendation_session = Column(Integer, default=0, nullable=False)

    # ---- Relationship ----
    user = relationship("User", back_populates="weakness_summary")

    def get_weakest_area(self) -> str:
        """Returns the single weakest category name."""
        scores = {
            "technical": self.technical_avg or 0,
            "communication": self.communication_avg or 0,
            "confidence": self.confidence_avg or 0,
            "relevance": self.relevance_avg or 0,
        }
        return min(scores, key=scores.get)

    def get_strongest_area(self) -> str:
        """Returns the single strongest category name."""
        scores = {
            "technical": self.technical_avg or 0,
            "communication": self.communication_avg or 0,
            "confidence": self.confidence_avg or 0,
            "relevance": self.relevance_avg or 0,
        }
        return max(scores, key=scores.get)

    def __repr__(self):
        return f"<WeaknessSummary user={self.user_id} | overall={self.overall_avg} | sessions={self.total_sessions}>"
