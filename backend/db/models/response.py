# ============================================
# db/models/response.py
# ============================================
# WHY THIS FILE EXISTS:
# Every question asked + answer given in an interview = one Response row.
# This is the most DATA-RICH table in the whole system.
# It stores:
#   - The question asked
#   - The user's answer (text + audio path)
#   - Stress signals detected
#   - Which interviewer persona was active
#   - GPT evaluation scores (relevance, clarity, confidence, technical)
#   - The ideal answer GPT would have given
#   - Identified strengths and weaknesses
#
# This table powers EVERYTHING:
#   - Dashboard charts
#   - Weakness tracking
#   - Adaptive interview (look at past weak areas)
#   - Session reports
# ============================================

from sqlalchemy import Column, String, Text, Float, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import BaseModel


class Response(BaseModel):
    __tablename__ = "responses"

    # ---- Foreign Key ----
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ---- Question Data ----
    question_number = Column(Integer, nullable=False)     # 1, 2, 3, 4, 5
    question_text = Column(Text, nullable=False)          # The actual question asked
    question_category = Column(String(100), nullable=True) # "technical" | "behavioral"
    question_difficulty = Column(String(50), nullable=True) # "easy" | "medium" | "hard"

    # ---- Answer Data ----
    # The user's answer — either typed or transcribed from audio
    answer_text = Column(Text, nullable=True)

    # Was this answer given via audio? (vs text typing)
    is_audio_answer = Column(Boolean, default=False, nullable=False)

    # Path to audio file if answered via microphone
    # (temporary path — audio deleted after transcription)
    audio_file_path = Column(String(500), nullable=True)

    # How long did the user take to answer? (milliseconds)
    # Used in stress calculation: long pause = stress signal
    response_latency_ms = Column(Integer, nullable=True)

    # ---- Stress Detection (Our Differentiator) ----
    # Raw stress signals extracted from the answer
    # Example: {"filler_count": 5, "hedge_count": 3, "wpm": 95, "brevity_penalty": 1}
    stress_signals = Column(JSON, nullable=True, default=dict)

    # Computed stress score (0-10, higher = more stressed)
    stress_score = Column(Float, nullable=True)

    # Which persona was active when this question was asked?
    # challenger | neutral | prober | supportive
    interviewer_persona = Column(String(50), nullable=True)

    # ---- GPT Evaluation Scores (0-10 each) ----
    # Overall score for this answer
    overall_score = Column(Float, nullable=True)

    # Breakdown by dimension:
    # Relevance: did they actually answer the question?
    relevance_score = Column(Float, nullable=True)

    # Clarity: was it easy to understand?
    clarity_score = Column(Float, nullable=True)

    # Confidence: did they sound sure of themselves?
    confidence_score = Column(Float, nullable=True)

    # Technical correctness: was the technical content accurate?
    technical_score = Column(Float, nullable=True)

    # ---- GPT Feedback ----
    # List of things done well
    # Example: ["Good use of STAR method", "Specific metrics mentioned"]
    strengths = Column(JSON, nullable=True, default=list)

    # List of things to improve
    # Example: ["Too vague on implementation details", "Used 'um' 8 times"]
    weaknesses = Column(JSON, nullable=True, default=list)

    # What GPT would have said as the ideal answer
    ideal_answer = Column(Text, nullable=True)

    # Short coaching tip for this specific answer
    coaching_tip = Column(Text, nullable=True)

    # ---- Relationship ----
    session = relationship("InterviewSession", back_populates="responses")

    def __repr__(self):
        return f"<Response Q{self.question_number} | score={self.overall_score} | stress={self.stress_score}>"
