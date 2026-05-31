# ============================================
# db/base.py
# ============================================
# WHY THIS FILE EXISTS:
# Every table in our database needs certain columns:
#   - id: unique identifier
#   - created_at: when was this row created
#   - updated_at: when was this row last changed
#
# Instead of copy-pasting these 3 columns into EVERY model,
# we define them ONCE here in a Base class.
# Every model then inherits from this.
#
# INHERITANCE EXAMPLE:
#   class User(BaseModel):    ← gets id, created_at, updated_at automatically
#       name = Column(String)
#       email = Column(String)
# ============================================

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from db.session import Base
import uuid


class BaseModel(Base):
    """
    Abstract base model — NOT a real table.
    Just a blueprint that other models inherit from.
    __abstract__ = True tells SQLAlchemy: don't create a table for THIS class.
    """
    __abstract__ = True

    # ---- Primary Key ----
    # UUID = Universally Unique Identifier
    # Example: "550e8400-e29b-41d4-a716-446655440000"
    #
    # WHY UUID instead of 1, 2, 3, 4...?
    # - Auto-increment integers are PREDICTABLE
    #   (anyone can guess user 5 exists if they see user 4)
    # - UUIDs are random = impossible to guess
    # - Safe to expose in URLs: /interview/550e8400... vs /interview/4
    # - Works across multiple database servers (no collision)
    #
    # default=uuid.uuid4 means: generate a new UUID automatically
    # when a new row is created — you never set this manually.
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # ---- Timestamps ----
    # server_default=func.now() means PostgreSQL sets this automatically.
    # Even if your Python code forgets to set it, the DB handles it.
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # onupdate=func.now() means: every time this row is updated,
    # PostgreSQL automatically updates this timestamp.
    # You never have to remember to update it in your code.
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict:
        """Convert model to dictionary (useful for API responses)."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
