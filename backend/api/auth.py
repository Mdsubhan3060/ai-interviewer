# ============================================
# api/auth.py
# ============================================
# WHY THIS FILE EXISTS:
# The frontend Login.jsx is currently using MOCK auth.
# This file provides the real backend auth endpoints
# that will be wired to Supabase in Step 11.
#
# For NOW (local dev) it returns a mock token so
# the frontend works end to end without Supabase.
#
# Step 11 will replace the mock with real Supabase JWT.
# ============================================

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


# ---- Request / Response schemas ----
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class OnboardingRequest(BaseModel):
    target_role: str
    years_experience: str


class AuthResponse(BaseModel):
    user_id: str
    email: str
    token: str
    is_new_user: bool


# ============================================
# POST /login  (mock — replace with Supabase)
# ============================================
@router.post("/login")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Mock login for local development.
    Creates user if not exists, returns mock JWT.

    Step 11: Replace with real Supabase JWT verification.
    """
    # Find or create user
    result = await db.execute(
        select(User).where(User.email == payload.email)
    )
    user = result.scalar_one_or_none()
    is_new = False

    if not user:
        # Create user on first login
        user = User(
            supabase_id=f"mock-{payload.email}",
            email=payload.email,
            full_name=payload.email.split("@")[0].title(),
        )
        db.add(user)
        await db.flush()
        is_new = True
        logger.info(f"Created new user: {user.email}")

    # Mock token = just the user ID for now
    # Step 11: Replace with real Supabase JWT
    mock_token = f"mock-jwt-{str(user.id)}"

    return {
        "user_id": str(user.id),
        "email": user.email,
        "token": mock_token,
        "is_new_user": is_new,
    }


# ============================================
# POST /onboarding
# ============================================
@router.post("/onboarding")
async def onboarding(
    payload: OnboardingRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Save target role and years experience after first login.
    Called from the onboarding screen (2 questions).
    """
    # NOTE: In Step 11, this will use get_current_user dependency.
    # For now it's open so local dev works without Supabase.
    return {"status": "ok", "message": "Onboarding saved"}


# ============================================
# GET /me
# ============================================
@router.get("/me")
async def get_me(
    db: AsyncSession = Depends(get_db),
):
    """
    Returns current user info.
    Step 11: Add get_current_user dependency.
    """
    return {"message": "Auth endpoint ready. Wire Supabase in Step 11."}
