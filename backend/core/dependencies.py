# ============================================
# core/dependencies.py
# ============================================
# Provides get_current_user(), the FastAPI dependency used by protected routes.
# It supports mock auth in development and Supabase Auth access tokens for real users.
# ============================================

import logging
from uuid import UUID
from typing import Optional

import httpx
from jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models.user import User
from db.session import get_db

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Return the authenticated local User for this request."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        if settings.is_development:
            logger.info("Mock auth: missing bearer token, using local dev user")
            return await _get_or_create_mock_user(db, "1")
        raise credentials_exception

    token = credentials.credentials

    if token.startswith("mock-jwt-"):
        if not settings.is_development:
            raise credentials_exception
        try:
            user_id_str = token.replace("mock-jwt-", "")
            return await _get_or_create_mock_user(db, user_id_str)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("Mock auth failed: %s", exc)
            raise credentials_exception

    supabase_user = await _verify_supabase_token(token)
    if not supabase_user and settings.SUPABASE_JWT_SECRET:
        supabase_user = _verify_supabase_jwt_locally(token)

    if not supabase_user:
        raise credentials_exception

    user = await _get_or_create_supabase_user(
        db=db,
        supabase_id=supabase_user["id"],
        email=supabase_user.get("email") or f"{supabase_user['id']}@supabase.local",
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    return user


async def _verify_supabase_token(token: str) -> Optional[dict]:
    """Verify a Supabase access token by asking Supabase Auth for the user."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        logger.warning("Supabase auth is not configured.")
        return None

    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user"
    headers = {
        "Authorization": f"Bearer {token}",
        "apikey": settings.SUPABASE_ANON_KEY,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("Supabase token verification request failed: %s", exc)
        return None

    if response.status_code != 200:
        logger.warning(
            "Supabase token verification failed: status=%s body=%s",
            response.status_code,
            response.text[:200],
        )
        return None

    data = response.json()
    return data if data.get("id") else None


def _verify_supabase_jwt_locally(token: str) -> Optional[dict]:
    """Optional fallback if SUPABASE_JWT_SECRET is configured later."""
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("Local JWT verification failed: %s", exc)
        return None

    supabase_id = payload.get("sub")
    if not supabase_id:
        return None

    return {"id": supabase_id, "email": payload.get("email")}


async def _get_or_create_supabase_user(
    db: AsyncSession,
    supabase_id: str,
    email: str,
) -> User:
    """Link a Supabase Auth user to this app's local User table."""
    result = await db.execute(select(User).where(User.supabase_id == supabase_id))
    user = result.scalar_one_or_none()
    if user:
        return user

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        user.supabase_id = supabase_id
        user.is_active = True
        await db.flush()
        return user

    user = User(
        supabase_id=supabase_id,
        email=email,
        full_name=email.split("@")[0].replace(".", " " ).title(),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    logger.info("Created local user for Supabase account %s", supabase_id)
    return user


async def _get_or_create_mock_user(db: AsyncSession, user_id_str: str) -> User:
    """Return a SQLAlchemy User for local mock auth."""
    try:
        user_uuid = UUID(user_id_str)
    except ValueError:
        user_uuid = None

    if user_uuid:
        result = await db.execute(select(User).where(User.id == user_uuid))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user

    mock_supabase_id = f"mock-{user_id_str}"
    result = await db.execute(
        select(User).where(User.supabase_id == mock_supabase_id)
    )
    user = result.scalar_one_or_none()

    if user and user.is_active:
        return user

    user = User(
        supabase_id=mock_supabase_id,
        email=f"local-dev-{user_id_str}@example.local",
        full_name="Local Dev User",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    logger.info("Mock auth: created local dev user %s", user.id)
    return user
