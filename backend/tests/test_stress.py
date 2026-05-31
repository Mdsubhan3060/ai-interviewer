# ============================================
# tests/test_stress.py
# ============================================

import pytest
from services.stress_service import (
    count_fillers,
    count_hedges,
    calculate_wpm,
    calculate_brevity_penalty,
    calculate_latency_penalty,
    compute_stress_score,
    select_persona,
)


class TestCountFillers:

    def test_no_fillers(self):
        text = "I implemented a REST API using FastAPI and PostgreSQL."
        assert count_fillers(text) == 0

    def test_single_filler(self):
        text = "I um implemented a REST API."
        assert count_fillers(text) == 1

    def test_multiple_fillers(self):
        text = "So um like I basically uh built this thing."
        assert count_fillers(text) >= 4

    def test_case_insensitive(self):
        text = "UM like BASICALLY you know."
        assert count_fillers(text) >= 3

    def test_empty_string(self):
        assert count_fillers("") == 0

    def test_multi_word_filler(self):
        text = "You know it works like this you know."
        count = count_fillers(text)
        assert count >= 2


class TestCountHedges:

    def test_no_hedges(self):
        text = "FastAPI uses async/await for high performance."
        assert count_hedges(text) == 0

    def test_single_hedge(self):
        text = "I think we should use PostgreSQL here."
        assert count_hedges(text) == 1

    def test_multiple_hedges(self):
        text = "I think maybe we could possibly use this approach."
        assert count_hedges(text) >= 2

    def test_not_sure_hedge(self):
        text = "I'm not sure but it might work."
        assert count_hedges(text) >= 1

    def test_empty_string(self):
        assert count_hedges("") == 0


class TestCalculateWPM:

    def test_normal_speech(self):
        """130 words in 60 seconds = 130 WPM"""
        text = " ".join(["word"] * 130)
        wpm = calculate_wpm(text, 60)
        assert wpm == pytest.approx(130.0, abs=1)

    def test_zero_duration(self):
        """Zero duration should return 0"""
        assert calculate_wpm("some text here", 0) == 0.0

    def test_fast_speech(self):
        """200 words in 60 seconds = 200 WPM"""
        text = " ".join(["word"] * 200)
        wpm = calculate_wpm(text, 60)
        assert wpm == pytest.approx(200.0, abs=1)


class TestBrevityPenalty:

    def test_long_behavioral_no_penalty(self):
        text = " ".join(["word"] * 150)
        assert calculate_brevity_penalty(text, "behavioral") == 0.0

    def test_very_short_behavioral_max_penalty(self):
        text = "It was good experience."
        assert calculate_brevity_penalty(text, "behavioral") == 3.0

    def test_long_technical_no_penalty(self):
        text = " ".join(["word"] * 60)
        assert calculate_brevity_penalty(text, "technical") == 0.0

    def test_very_short_technical_max_penalty(self):
        text = "Yes it works."
        assert calculate_brevity_penalty(text, "technical") == 3.0


class TestLatencyPenalty:

    def test_no_latency(self):
        assert calculate_latency_penalty(0) == 0.0

    def test_fast_response(self):
        """Under 3 seconds = no penalty"""
        assert calculate_latency_penalty(2000) == 0.0

    def test_slight_hesitation(self):
        """3-6 seconds = small penalty"""
        assert calculate_latency_penalty(4000) == 0.5

    def test_long_pause(self):
        """10-20 seconds = bigger penalty"""
        assert calculate_latency_penalty(15000) == 1.5

    def test_very_long_pause(self):
        """20+ seconds = max penalty"""
        assert calculate_latency_penalty(25000) == 2.0


class TestSelectPersona:

    def test_low_stress_challenger(self):
        assert select_persona(0.0) == "challenger"
        assert select_persona(3.0) == "challenger"

    def test_medium_stress_neutral(self):
        assert select_persona(4.0) == "neutral"
        assert select_persona(6.0) == "neutral"

    def test_high_stress_prober(self):
        assert select_persona(7.0) == "prober"
        assert select_persona(8.0) == "prober"

    def test_very_high_stress_supportive(self):
        assert select_persona(9.0) == "supportive"
        assert select_persona(10.0) == "supportive"


class TestComputeStressScore:

    def test_confident_answer(self):
        """Clean answer with no fillers = low stress"""
        text = (
            "I designed a microservices architecture using FastAPI. "
            "Each service had its own PostgreSQL database. "
            "We used Redis for caching and RabbitMQ for messaging. "
            "The system handled 10,000 requests per second."
        )
        result = compute_stress_score(text, duration_seconds=15)
        assert result["stress_score"] <= 4.0
        assert result["persona"] in ["challenger", "neutral"]

    def test_nervous_answer(self):
        """Answer full of fillers and hedges = high stress"""
        text = (
            "Um so I think like maybe I used uh you know "
            "basically some kind of database I'm not sure "
            "um it might have been PostgreSQL or maybe not."
        )
        result = compute_stress_score(text, duration_seconds=20)
        assert result["stress_score"] >= 5.0

    def test_empty_answer(self):
        """Empty answer = default neutral"""
        result = compute_stress_score("")
        assert result["stress_score"] == 5.0
        assert result["persona"] == "neutral"

    def test_returns_required_fields(self):
        """Result must have all required fields"""
        result = compute_stress_score("I built a REST API.", duration_seconds=5)
        assert "stress_score" in result
        assert "signals" in result
        assert "persona" in result
        assert "persona_details" in result

    def test_score_in_range(self):
        """Score must always be 0-10"""
        text = "um um um um uh uh like basically you know I think maybe"
        result = compute_stress_score(text, duration_seconds=5)
        assert 0 <= result["stress_score"] <= 10
