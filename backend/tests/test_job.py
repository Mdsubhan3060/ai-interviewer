# ============================================
# tests/test_job.py
# ============================================

import pytest
from services.job_service import cosine_similarity, calculate_final_score


class TestCosineSimilarity:

    def test_identical_vectors(self):
        """Same vector = similarity 1.0"""
        vec = [1.0, 0.0, 0.0, 0.5]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0, abs=0.001)

    def test_zero_vector(self):
        """Zero vector = similarity 0.0 (no crash)"""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 0.5, 0.3]
        assert cosine_similarity(vec1, vec2) == 0.0

    def test_similar_vectors(self):
        """Similar vectors = high similarity"""
        vec1 = [1.0, 1.0, 0.0]
        vec2 = [1.0, 0.9, 0.1]
        score = cosine_similarity(vec1, vec2)
        assert score > 0.9

    def test_unrelated_vectors(self):
        """Perpendicular vectors = 0 similarity"""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0, abs=0.001)

    def test_returns_float(self):
        """Result must be a float"""
        result = cosine_similarity([1.0, 0.5], [0.5, 1.0])
        assert isinstance(result, float)

    def test_score_between_0_and_1(self):
        """Score must always be between 0 and 1"""
        vec1 = [0.5, 0.3, 0.8, 0.1]
        vec2 = [0.2, 0.9, 0.4, 0.7]
        score = cosine_similarity(vec1, vec2)
        assert 0.0 <= score <= 1.0


class TestCalculateFinalScore:

    def test_perfect_match(self):
        """All 100s = score near 100"""
        score = calculate_final_score(1.0, 100, 100, 100)
        assert score == pytest.approx(100.0, abs=0.1)

    def test_zero_match(self):
        """All zeros = score 0"""
        score = calculate_final_score(0.0, 0, 0, 0)
        assert score == 0.0

    def test_weights_add_up(self):
        """
        Weights: similarity=40%, skill=35%, exp=15%, edu=10%
        Test: only similarity=1.0, rest=0 → score should be 40
        """
        score = calculate_final_score(1.0, 0, 0, 0)
        assert score == pytest.approx(40.0, abs=0.1)

    def test_skill_weight(self):
        """Only skill_match=100, rest=0 → score should be 35"""
        score = calculate_final_score(0.0, 100, 0, 0)
        assert score == pytest.approx(35.0, abs=0.1)

    def test_realistic_score(self):
        """Realistic inputs should return sensible score"""
        score = calculate_final_score(0.75, 70, 80, 90)
        assert 60 <= score <= 85

    def test_returns_rounded(self):
        """Score should be rounded to 1 decimal"""
        score = calculate_final_score(0.723, 68, 75, 82)
        assert score == round(score, 1)
