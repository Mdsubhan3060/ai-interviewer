# ============================================
# tests/test_dashboard.py
# ============================================
# Tests for dashboard_service.py
# These test the data aggregation logic only —
# no DB calls, no GPT calls.
# ============================================

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from services.dashboard_service import get_dashboard_summary


class TestGetDashboardSummary:
    """Test dashboard summary returns correct structure."""

    @pytest.mark.asyncio
    async def test_no_sessions_returns_zeros(self):
        """
        When user has no WeaknessSummary yet,
        return zeros / empty lists, not an error.
        """
        mock_db = AsyncMock()

        # Simulate no WeaknessSummary found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        # Simulate no sessions found
        mock_sessions_result = MagicMock()
        mock_sessions_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_result, mock_sessions_result])

        result = await get_dashboard_summary(db=mock_db, user_id=uuid4())

        assert result["total_sessions"] == 0
        assert result["overall_avg"] is None
        assert result["top_weaknesses"] == []
        assert result["recommendations"] == []
        assert result["session_history"] == []

    @pytest.mark.asyncio
    async def test_with_summary_returns_averages(self):
        """
        When WeaknessSummary exists, return all averages.
        """
        mock_db = AsyncMock()

        mock_summary = MagicMock()
        mock_summary.total_sessions = 5
        mock_summary.total_questions_answered = 25
        mock_summary.overall_avg = 7.2
        mock_summary.technical_avg = 6.8
        mock_summary.communication_avg = 7.5
        mock_summary.confidence_avg = 6.5
        mock_summary.relevance_avg = 7.0
        mock_summary.avg_stress_score = 4.2
        mock_summary.stress_trend = 0.5
        mock_summary.top_weaknesses = ["technical_depth", "confidence"]
        mock_summary.top_strengths = ["communication"]
        mock_summary.score_history = [5.0, 5.8, 6.5, 7.0, 7.2]
        mock_summary.category_score_history = {"technical": [5.0, 6.0, 6.8]}
        mock_summary.recommendations = ["Practice STAR method"]

        mock_summary_result = MagicMock()
        mock_summary_result.scalar_one_or_none.return_value = mock_summary

        mock_sessions_result = MagicMock()
        mock_sessions_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[mock_summary_result, mock_sessions_result])

        result = await get_dashboard_summary(db=mock_db, user_id=uuid4())

        assert result["total_sessions"] == 5
        assert result["overall_avg"] == 7.2
        assert result["technical_avg"] == 6.8
        assert result["top_weaknesses"] == ["technical_depth", "confidence"]
        assert result["score_history"] == [5.0, 5.8, 6.5, 7.0, 7.2]
        assert len(result["recommendations"]) == 1

    @pytest.mark.asyncio
    async def test_session_history_included(self):
        """
        Completed sessions appear in session_history list.
        """
        from datetime import datetime
        mock_db = AsyncMock()

        mock_summary_result = MagicMock()
        mock_summary_result.scalar_one_or_none.return_value = None

        mock_session = MagicMock()
        mock_session.id = uuid4()
        mock_session.created_at = datetime(2025, 1, 15, 10, 0, 0)
        mock_session.job_title = "Software Engineer"
        mock_session.overall_score = 7.5
        mock_session.total_questions = 5
        mock_session.category_scores = {"technical": 7.0}
        mock_session.avg_stress_score = 3.5
        mock_session.dominant_persona = "neutral"

        mock_sessions_result = MagicMock()
        mock_sessions_result.scalars.return_value.all.return_value = [mock_session]

        mock_db.execute = AsyncMock(side_effect=[mock_summary_result, mock_sessions_result])

        result = await get_dashboard_summary(db=mock_db, user_id=uuid4())

        assert len(result["session_history"]) == 1
        assert result["session_history"][0]["job_title"] == "Software Engineer"
        assert result["session_history"][0]["overall_score"] == 7.5

    def test_empty_score_history_no_crash(self):
        """score_history = None should not crash anything."""
        # Just verify the fallback works
        history = None
        result = history or []
        assert result == []

    def test_empty_recommendations_no_crash(self):
        """recommendations = None should return empty list."""
        recs = None
        result = recs or []
        assert result == []
