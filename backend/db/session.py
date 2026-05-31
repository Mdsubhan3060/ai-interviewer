# ============================================
# db/session.py
# ============================================
# WHY THIS FILE EXISTS:
# This file manages your PostgreSQL connection.
#
# KEY CONCEPT - Connection Pool:
# Opening a new database connection for EVERY request is slow and expensive.
# A "connection pool" keeps N connections open and REUSES them.
# SQLAlchemy manages this automatically with create_async_engine.
#
# KEY CONCEPT - Async:
# "async" means your API doesn't WAIT for the database.
# While waiting for DB response, it can handle other requests.
# This is why we use asyncpg (async PostgreSQL driver).
# A synchronous server would freeze waiting for DB on every request.
# ============================================

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import logging

from core.config import settings

logger = logging.getLogger(__name__)


# ============================================
# Database Engine
# ============================================
# The "engine" is the core connection object.
# pool_size=10: Keep 10 connections open at all times
# max_overflow=20: Allow up to 20 extra connections during traffic spikes
# pool_pre_ping=True: Test connections before using (handles dropped connections)
# echo=True in dev: Prints every SQL query to terminal (useful for debugging)
# ============================================
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=settings.DEBUG,  # Log SQL in development only
)


# ============================================
# Session Factory
# ============================================
# A "session" is one unit of work with the database.
# Think of it like a shopping cart:
#   - You add items (DB operations)
#   - You commit() = checkout (save everything)
#   - Or rollback() = abandon cart (undo everything)
#
# async_sessionmaker creates new sessions on demand.
# expire_on_commit=False: Keep objects usable after commit
# (without this, accessing object attributes after commit causes another DB query)
# ============================================
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ============================================
# Base Model Class
# ============================================
# ALL database models inherit from this.
# Provides SQLAlchemy's ORM features (Column, relationship, etc.)
# We'll add shared columns (id, created_at) here in Step 2.
# ============================================
class Base(DeclarativeBase):
    pass


# ============================================
# Database Initialization
# ============================================
# Called ONCE at startup (from main.py lifespan).
# Creates all tables that don't exist yet.
# In production, we use Alembic migrations instead (more controlled).
# ============================================
async def init_db():
    """Create all tables and verify database connection."""
    try:
        async with engine.begin() as conn:
            # Test the connection
            await conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection verified")

            # Create tables (only creates if they don't exist)
            # In production: use `alembic upgrade head` instead
            await conn.run_sync(Base.metadata.create_all)
            await _sync_dev_schema(conn)
            logger.info("✅ Database tables ready")

    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise


async def _sync_dev_schema(conn):
    """Apply tiny idempotent schema updates for local create_all-based dev DBs."""
    if not settings.is_development:
        return

    await conn.execute(text(
        "ALTER TABLE resumes "
        "ADD COLUMN IF NOT EXISTS blob_url VARCHAR(500)"
    ))
    await conn.execute(text(
        "ALTER TABLE resumes "
        "ADD COLUMN IF NOT EXISTS experience_label VARCHAR(100)"
    ))
    await conn.execute(text(
        "ALTER TABLE resumes "
        "ADD COLUMN IF NOT EXISTS experience_months INTEGER"
    ))


# ============================================
# Dependency Injection - get_db()
# ============================================
# HOW FASTAPI DEPENDENCY INJECTION WORKS:
#
# Instead of creating a DB session manually in every endpoint,
# FastAPI automatically calls get_db() and passes the session in.
#
# Example usage in a route:
#   async def my_endpoint(db: AsyncSession = Depends(get_db)):
#       result = await db.execute(select(User))
#
# The "async with" + "finally" pattern ensures:
#   - Session is always closed after the request (no connection leaks)
#   - If an error occurs, changes are rolled back automatically
#   - Whether the endpoint succeeds or fails, cleanup happens
# ============================================
async def get_db() -> AsyncSession:
    """
    Dependency that provides a database session per request.
    Automatically closes the session when the request is done.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
