# ============================================
# tests/test_evaluation.py
# ============================================

import pytest
from services.evaluation_service import (
    _fallback_evaluation,
    calculate_category_scores,
)
from unittest.mock import MagicMock


class TestFallbackEvaluation:

    def test_returns_all_fields(self):
        """Fallback must have all required fields"""
        result = _fallback_evaluation("My answer here")
        required = [
            "overall_score", "relevance_score", "clarity_score",
            "confidence_score", "technical_score", "strengths",
            "weaknesses", "ideal_answer", "coaching_tip",
        ]
        for field in required:
            assert field in result

    def test_scores_in_range(self):
        """All scores must be 0-10"""
        result = _fallback_evaluation("Some answer text here")
        for key in ["overall_score", "relevance_score",
                    "clarity_score", "confidence_score", "technical_score"]:
            assert 0 <= result[key] <= 10

    def test_empty_answer(self):
        """Empty answer returns score 0"""
        result = _fallback_evaluation("")
        assert result["overall_score"] == 0.0

    def test_long_answer_higher_score(self):
        """Longer answer gets higher fallback score"""
        short = _fallback_evaluation("Short answer.")
        long = _fallback_evaluation(
            "This is a much longer and more detailed answer "
            "that covers multiple aspects of the question "
            "with specific examples and technical depth. " * 5
        )
        assert long["overall_score"] >= short["overall_score"]

    def test_score_capped_at_7(self):
        """Fallback score never exceeds 7.0"""
        very_long = "word " * 500
        result = _fallback_evaluation(very_long)
        assert result["overall_score"] <= 7.0

    def test_strengths_is_list(self):
        result = _fallback_evaluation("Some answer")
        assert isinstance(result["strengths"], list)

    def test_weaknesses_is_list(self):
        result = _fallback_evaluation("Some answer")
        assert isinstance(result["weaknesses"], list)


class TestCalculateCategoryScores:

    def _make_response(self, overall, technical, clarity, confidence, relevance):
        """Helper to create mock Response objects"""
        r = MagicMock()
        r.overall_score = overall
        r.technical_score = technical
        r.clarity_score = clarity
        r.confidence_score = confidence
        r.relevance_score = relevance
        return r

    def test_empty_responses(self):
        """No responses = empty dict"""
        result = calculate_category_scores([])
        assert result == {}

    def test_single_response(self):
        """Single response calculates correctly"""
        r = self._make_response(8.0, 9.0, 7.0, 8.0, 8.0)
        result = calculate_category_scores([r])
        assert result["overall"] == 8.0
        assert result["technical"] == 9.0

    def test_multiple_responses_average(self):
        """Multiple responses averaged correctly"""
        r1 = self._make_response(6.0, 6.0, 6.0, 6.0, 6.0)
        r2 = self._make_response(8.0, 8.0, 8.0, 8.0, 8.0)
        result = calculate_category_scores([r1, r2])
        assert result["overall"] == 7.0
        assert result["technical"] == 7.0

    def test_unanswered_responses_excluded(self):
        """Responses without scores are excluded"""
        r1 = self._make_response(8.0, 8.0, 8.0, 8.0, 8.0)
        r2 = self._make_response(None, None, None, None, None)
        result = calculate_category_scores([r1, r2])
        # Only r1 counts
        assert result["overall"] == 8.0

    def test_returns_all_categories(self):
        """Result has all category keys"""
        r = self._make_response(7.0, 7.0, 7.0, 7.0, 7.0)
        result = calculate_category_scores([r])
        for key in ["overall", "technical", "clarity", "confidence", "relevance"]:
            assert key in result
