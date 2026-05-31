# ============================================
# db/models/user.py
# ============================================
# WHY THIS FILE EXISTS:
# The User table is the ROOT of everything.
# Every resume, session, and response belongs to a user.
#
# IMPORTANT: We use Supabase for authentication.
# This means Supabase handles:
#   - Password storage (we NEVER store passwords)
#   - Login / logout
#   - JWT token generation
#
# Our User table just stores PROFILE INFO and links
# to Supabase via supabase_id (their UUID from Supabase).
# ============================================

from sqlalchemy import Column, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    # ---- Supabase Link ----
    # When a user logs in via Supabase, we get their Supabase UUID.
    # We store it here to link OUR data to THEIR auth account.
    # unique=True: one Supabase account = one user profile
    # index=True: makes lookups by supabase_id FAST
    #   (without index: DB scans every row to find the match)
    #   (with index: DB jumps directly to the match)
    supabase_id = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # ---- Profile Info ----
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Target job title (used to personalize interview questions)
    # Example: "Senior Python Developer", "Data Scientist"
    target_role = Column(String(255), nullable=True)

    # Years of experience (helps calibrate question difficulty)
    years_experience = Column(String(50), nullable=True)  # "2-3", "5+", etc.

    # Is this account active? False = soft delete (don't actually delete data)
    is_active = Column(Boolean, default=True, nullable=False)

    # ---- Relationships ----
    # "relationship" tells SQLAlchemy HOW tables connect.
    # back_populates = the matching relationship on the OTHER model.
    #
    # cascade="all, delete-orphan" means:
    # If a User is deleted, automatically delete all their resumes too.
    # Without this: deleting a user would leave orphaned resumes in DB.
    resumes = relationship(
        "Resume",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    sessions = relationship(
        "InterviewSession",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    weakness_summary = relationship(
        "WeaknessSummary",
        back_populates="user",
        uselist=False,          # One-to-one: each user has ONE summary
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User {self.email}>"
