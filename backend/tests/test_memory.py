# ============================================
# tests/test_memory.py
# ============================================

import pytest
from services.memory_service import (
    update_running_average,
    identify_weak_areas,
    calculate_stress_trend,
)


class TestUpdateRunningAverage:

    def test_first_session(self):
        """First session — no old average"""
        result = update_running_average(None, 0, 7.0)
        assert result == 7.0

    def test_second_session(self):
        """Two sessions averaged correctly"""
        result = update_running_average(6.0, 1, 8.0)
        assert result == 7.0

    def test_running_average_formula(self):
        """(5*3 + 7) / 4 = 5.5"""
        result = update_running_average(5.0, 3, 7.0)
        assert result == 5.5

    def test_same_score(self):
        """Same score = average stays same"""
        result = update_running_average(6.0, 5, 6.0)
        assert result == 6.0

    def test_improving_trend(self):
        """New high score raises average"""
        result = update_running_average(5.0, 4, 9.0)
        assert result > 5.0

    def test_declining_trend(self):
        """New low score lowers average"""
        result = update_running_average(8.0, 4, 2.0)
        assert result < 8.0

    def test_returns_rounded(self):
        """Result rounded to 2 decimal places"""
        result = update_running_average(5.0, 3, 7.0)
        assert result == round(result, 2)

    def test_zero_old_count(self):
        """Zero count treated as first session"""
        result = update_running_average(5.0, 0, 7.0)
        assert result == 7.0


class TestIdentifyWeakAreas:

    def test_all_weak(self):
        """All scores below 6 = all weak"""
        weak, strong = identify_weak_areas(4.0, 4.0, 4.0, 4.0)
        assert len(weak) > 0
        assert len(strong) == 0

    def test_all_strong(self):
        """All scores above 7.5 = all strong"""
        weak, strong = identify_weak_areas(8.0, 8.0, 8.0, 8.0)
        assert len(weak) == 0
        assert len(strong) > 0

    def test_mixed_scores(self):
        """Low technical = technical in weak areas"""
        weak, strong = identify_weak_areas(3.0, 8.0, 8.0, 8.0)
        assert "technical_depth" in weak

    def test_max_3_weak_areas(self):
        """Never returns more than 3 weak areas"""
        weak, _ = identify_weak_areas(2.0, 2.0, 2.0, 2.0)
        assert len(weak) <= 3

    def test_none_scores(self):
        """None scores treated as 0"""
        weak, strong = identify_weak_areas(None, None, None, None)
        assert len(weak) > 0

    def test_returns_strings(self):
        """Weak areas are strings"""
        weak, strong = identify_weak_areas(3.0, 7.0, 8.0, 6.0)
        for area in weak:
            assert isinstance(area, str)


class TestCalculateStressTrend:

    def test_not_enough_data(self):
        """Less than 4 sessions = no trend"""
        assert calculate_stress_trend([5.0, 6.0]) == 0.0
        assert calculate_stress_trend([]) == 0.0

    def test_improving_trend(self):
        """Stress decreasing over time = positive trend"""
        # Old sessions: high stress, recent: low stress
        scores = [8.0, 8.0, 7.0, 7.0, 3.0, 3.0, 2.0, 2.0]
        trend = calculate_stress_trend(scores)
        assert trend > 0  # Positive = improving (less stressed)

    def test_worsening_trend(self):
        """Stress increasing over time = negative trend"""
        scores = [2.0, 2.0, 3.0, 3.0, 7.0, 7.0, 8.0, 8.0]
        trend = calculate_stress_trend(scores)
        assert trend < 0  # Negative = worsening (more stressed)

    def test_stable_trend(self):
        """Consistent stress = trend near 0"""
        scores = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        trend = calculate_stress_trend(scores)
        assert trend == pytest.approx(0.0, abs=0.1)

    def test_returns_float(self):
        """Always returns a float"""
        result = calculate_stress_trend([5.0, 6.0, 4.0, 5.0])
        assert isinstance(result, float)
