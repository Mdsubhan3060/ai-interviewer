# ============================================
# db/models/__init__.py
# ============================================
# WHY THIS FILE EXISTS:
# SQLAlchemy needs to KNOW about all models before it can
# create the tables. If a model isn't imported here,
# its table won't be created when you run migrations.
#
# Think of it as a "register" — every model signs in here.
#
# The order matters for foreign keys:
# User must exist before Resume (Resume references User)
# Resume must exist before InterviewSession (Session references Resume)
# InterviewSession must exist before Response (Response references Session)
# ============================================

from db.models.user import User
from db.models.resume import Resume
from db.models.interview_session import InterviewSession, SessionStatus, InterviewType
from db.models.response import Response
from db.models.weakness_summary import WeaknessSummary
from db.models.job_match import JobMatch

# Export everything for easy importing elsewhere:
# from db.models import User, Resume, InterviewSession
__all__ = [
    "User",
    "Resume",
    "InterviewSession",
    "SessionStatus",
    "InterviewType",
    "Response",
    "WeaknessSummary",
    "JobMatch",
]
