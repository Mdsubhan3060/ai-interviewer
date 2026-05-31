# ============================================
# services/stress_service.py
# ============================================
# WHY THIS FILE EXISTS:
# This is THE DIFFERENTIATOR of our entire project.
# No other mock interview tool does this.
#
# WHAT IT DOES:
# Analyzes a candidate's answer for stress signals,
# computes a stress score, then selects an interviewer
# persona that adapts to how stressed the candidate is.
#
# REAL INTERVIEWS WORK THIS WAY:
# A good interviewer READS the candidate.
# If you're nervous → they slow down and rephrase.
# If you're confident → they push harder.
# Our AI does exactly this automatically.
#
# STRESS SIGNALS WE DETECT:
# 1. Filler words    → "um", "uh", "like", "basically"
#                      High count = nervous, buying time
# 2. Hedge words     → "I think", "maybe", "not sure"
#                      High count = low confidence
# 3. Words per min   → very slow or very fast = stress
#                      Normal range: 120-160 WPM
# 4. Brevity penalty → answer too short for the question
#                      Indicates avoidance or confusion
# 5. Response latency→ long pause before answering
#                      (measured in frontend, passed here)
# ============================================

import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ============================================
# Stress Signal Constants
# ============================================

# Words that indicate nervousness / buying time
FILLER_WORDS = {
    "um", "uh", "umm", "uhh", "er", "err",
    "like", "basically", "literally", "actually",
    "you know", "i mean", "right", "so", "well",
    "kind of", "sort of", "kinda", "sorta",
}

# Phrases that indicate low confidence / uncertainty
HEDGE_PHRASES = [
    "i think", "i believe", "i guess", "i suppose",
    "maybe", "perhaps", "possibly", "probably",
    "not sure", "not certain", "not sure if",
    "i'm not sure", "i don't know", "i'm not certain",
    "it might be", "it could be", "i'm not 100%",
    "if i remember correctly", "if i recall",
]

# Normal speaking rate range (words per minute)
WPM_TOO_SLOW = 80    # Below this = very nervous/hesitant
WPM_NORMAL_LOW = 110  # Lower bound of natural speech
WPM_NORMAL_HIGH = 170 # Upper bound of natural speech
WPM_TOO_FAST = 200   # Above this = rushing/nervous


# ============================================
# Persona Definitions
# ============================================
# These are injected into GPT's system prompt
# when generating the NEXT question.
# The tone of the next question changes based on stress.

PERSONAS = {
    "challenger": {
        "name": "Challenger",
        "description": "Candidate is confident. Push harder.",
        "system_prompt": (
            "You are a senior FAANG interviewer known for being rigorous. "
            "The candidate is performing well and seems confident. "
            "Push back on their answers. Ask 'why' and 'what if' aggressively. "
            "Challenge their assumptions. Raise the difficulty bar. "
            "Ask follow-up questions that test depth of knowledge."
        ),
        "tone": "challenging and probing",
    },
    "neutral": {
        "name": "Neutral",
        "description": "Candidate is doing fine. Standard interview.",
        "system_prompt": (
            "You are a professional interviewer conducting a standard technical interview. "
            "Ask clear, focused questions. Be professional but not harsh. "
            "Follow up naturally if the answer is incomplete. "
            "Maintain a neutral, evaluative tone."
        ),
        "tone": "professional and neutral",
    },
    "prober": {
        "name": "Prober",
        "description": "Candidate seems hesitant. Slow down, dig deeper.",
        "system_prompt": (
            "You are a patient interviewer. The candidate seems a bit hesitant "
            "but may have the knowledge — they just need help expressing it. "
            "Ask one focused clarifying question at a time. "
            "Break complex questions into smaller parts. "
            "Use phrases like 'Can you walk me through...' or 'Tell me more about...'. "
            "Give them space to think."
        ),
        "tone": "patient and clarifying",
    },
    "supportive": {
        "name": "Supportive",
        "description": "Candidate is struggling. Encourage and reframe.",
        "system_prompt": (
            "You are an encouraging interviewer. The candidate is clearly stressed "
            "and struggling. Your goal is to help them show their best self. "
            "Reframe questions more simply. Offer context clues without giving the answer. "
            "Use encouraging phrases like 'Good start, can you expand on...' "
            "or 'You're on the right track, what about...'. "
            "Never make them feel bad for not knowing something."
        ),
        "tone": "warm and encouraging",
    },
}


# ============================================
# Stress Signals Dataclass
# ============================================
@dataclass
class StressSignals:
    """
    Raw stress signals extracted from an answer.
    A dataclass = a simple container for related data.
    Like a Python dict but with type hints and dot access.
    """
    filler_count: int          # Number of filler words used
    filler_rate: float         # Fillers per 100 words
    hedge_count: int           # Number of hedge phrases used
    hedge_rate: float          # Hedges per 100 words
    word_count: int            # Total words in answer
    words_per_minute: float    # Speaking rate (if duration known)
    brevity_penalty: float     # 0-3 based on how short the answer is
    latency_penalty: float     # 0-2 based on response delay


# ============================================
# FUNCTION 1: Count Filler Words
# ============================================
def count_fillers(text: str) -> int:
    """
    Count filler words in text.

    Approach:
    - Convert to lowercase
    - Split into words and check each word
    - Also check multi-word fillers ("you know", "kind of")

    Args:
        text: Transcribed answer text

    Returns:
        Total filler word count
    """
    text_lower = text.lower()
    count = 0

    # Check single-word fillers
    words = re.findall(r'\b\w+\b', text_lower)
    for word in words:
        if word in FILLER_WORDS:
            count += 1

    # Check multi-word fillers ("you know", "kind of", etc.)
    multi_word_fillers = [f for f in FILLER_WORDS if " " in f]
    for phrase in multi_word_fillers:
        count += text_lower.count(phrase)

    return count


# ============================================
# FUNCTION 2: Count Hedge Phrases
# ============================================
def count_hedges(text: str) -> int:
    """
    Count confidence-reducing hedge phrases.

    Args:
        text: Transcribed answer text

    Returns:
        Total hedge phrase count
    """
    text_lower = text.lower()
    count = 0
    for phrase in HEDGE_PHRASES:
        count += text_lower.count(phrase)
    return count


# ============================================
# FUNCTION 3: Calculate Words Per Minute
# ============================================
def calculate_wpm(text: str, duration_seconds: float) -> float:
    """
    Calculate speaking rate in words per minute.

    WHY WPM MATTERS:
    Normal conversational speech = 120-170 WPM
    Very slow speech (<80 WPM) = hesitant, nervous
    Very fast speech (>200 WPM) = rushing, anxiety

    Args:
        text: Transcribed text
        duration_seconds: Audio duration in seconds

    Returns:
        Words per minute (float)
    """
    if duration_seconds <= 0:
        return 0.0

    word_count = len(text.split())
    wpm = (word_count / duration_seconds) * 60
    return round(wpm, 1)


# ============================================
# FUNCTION 4: Calculate Brevity Penalty
# ============================================
def calculate_brevity_penalty(
    text: str,
    question_category: str = "technical",
) -> float:
    """
    Penalize answers that are too short.

    WHY SHORT ANSWERS = STRESS SIGNAL:
    A nervous candidate often gives vague, brief answers
    to avoid saying something wrong.
    A confident candidate elaborates naturally.

    Expected word counts:
    - behavioral: 100-300 words (tell me about a time...)
    - technical:  50-200 words (explain this concept)
    - easy:       30-100 words

    Args:
        text: Answer text
        question_category: "technical" or "behavioral"

    Returns:
        Penalty score 0-3 (higher = more penalty)
    """
    word_count = len(text.split())

    if question_category == "behavioral":
        if word_count < 30:
            return 3.0   # Very short behavioral answer = big red flag
        elif word_count < 60:
            return 2.0
        elif word_count < 100:
            return 1.0
        else:
            return 0.0
    else:  # technical
        if word_count < 15:
            return 3.0
        elif word_count < 30:
            return 2.0
        elif word_count < 50:
            return 1.0
        else:
            return 0.0


# ============================================
# FUNCTION 5: Calculate Latency Penalty
# ============================================
def calculate_latency_penalty(latency_ms: int) -> float:
    """
    Penalize very long pauses before answering.

    Normal thinking time = 2-5 seconds (2000-5000ms)
    Long pause = 5-10 seconds (nervous, blanking)
    Very long pause = 10+ seconds (really struggling)

    Args:
        latency_ms: Milliseconds between question shown and answer started

    Returns:
        Penalty 0-2
    """
    if latency_ms <= 0:
        return 0.0  # No latency data

    if latency_ms < 3000:      # Under 3 seconds = fine
        return 0.0
    elif latency_ms < 6000:    # 3-6 seconds = slight hesitation
        return 0.5
    elif latency_ms < 10000:   # 6-10 seconds = noticeable pause
        return 1.0
    elif latency_ms < 20000:   # 10-20 seconds = long pause
        return 1.5
    else:                       # 20+ seconds = very long pause
        return 2.0


# ============================================
# FUNCTION 6: Compute Stress Score
# ============================================
def compute_stress_score(
    text: str,
    duration_seconds: float = 0,
    latency_ms: int = 0,
    question_category: str = "technical",
) -> dict:
    """
    Compute overall stress score from all signals.

    SCORING FORMULA:
    Each signal contributes to a raw stress score.
    We then normalize to 0-10 scale.

    Weights:
    - Filler rate:      30% (strongest stress signal)
    - Hedge rate:       25% (confidence indicator)
    - WPM deviation:    20% (speaking pace)
    - Brevity penalty:  15% (answer length)
    - Latency penalty:  10% (thinking time)

    Args:
        text: Transcribed answer text
        duration_seconds: Audio duration
        latency_ms: Time before answering
        question_category: technical/behavioral

    Returns:
        Dict with stress_score, signals, persona
    """
    if not text or not text.strip():
        return {
            "stress_score": 5.0,
            "signals": {},
            "persona": "neutral",
            "persona_details": PERSONAS["neutral"],
        }

    words = text.split()
    word_count = len(words)

    # ---- Extract Signals ----
    filler_count = count_fillers(text)
    hedge_count = count_hedges(text)

    # Rate per 100 words (normalized for answer length)
    filler_rate = (filler_count / word_count * 100) if word_count > 0 else 0
    hedge_rate = (hedge_count / word_count * 100) if word_count > 0 else 0

    # WPM
    wpm = calculate_wpm(text, duration_seconds) if duration_seconds > 0 else 130

    # WPM stress: how far from normal range?
    if WPM_NORMAL_LOW <= wpm <= WPM_NORMAL_HIGH:
        wpm_stress = 0.0  # Normal speaking rate
    elif wpm < WPM_TOO_SLOW:
        wpm_stress = 3.0  # Very slow = stressed
    elif wpm < WPM_NORMAL_LOW:
        wpm_stress = 1.5  # Slightly slow
    elif wpm > WPM_TOO_FAST:
        wpm_stress = 2.5  # Very fast = rushing
    else:
        wpm_stress = 1.0  # Slightly fast

    brevity_penalty = calculate_brevity_penalty(text, question_category)
    latency_penalty = calculate_latency_penalty(latency_ms)

    # ---- Calculate Raw Stress Score ----
    # Each component scored 0-10
    filler_component  = min(filler_rate * 2, 10)   # >5 fillers per 100 words = max stress
    hedge_component   = min(hedge_rate * 2.5, 10)  # >4 hedges per 100 words = max stress
    wpm_component     = min(wpm_stress * 3, 10)
    brevity_component = min(brevity_penalty * 3, 10)
    latency_component = min(latency_penalty * 5, 10)

    # Weighted average
    raw_score = (
        filler_component  * 0.30 +
        hedge_component   * 0.25 +
        wpm_component     * 0.20 +
        brevity_component * 0.15 +
        latency_component * 0.10
    )

    # Round to 1 decimal
    stress_score = round(min(raw_score, 10.0), 1)

    # ---- Select Persona ----
    persona = select_persona(stress_score)

    # ---- Build Signals Dict (for storage in DB) ----
    signals = {
        "filler_count": filler_count,
        "filler_rate": round(filler_rate, 2),
        "hedge_count": hedge_count,
        "hedge_rate": round(hedge_rate, 2),
        "word_count": word_count,
        "words_per_minute": wpm,
        "brevity_penalty": brevity_penalty,
        "latency_penalty": latency_penalty,
        "wpm_stress": wpm_stress,
    }

    logger.info(
        f"Stress score: {stress_score} | "
        f"Fillers: {filler_count} | "
        f"Hedges: {hedge_count} | "
        f"WPM: {wpm} | "
        f"Persona: {persona}"
    )

    return {
        "stress_score": stress_score,
        "signals": signals,
        "persona": persona,
        "persona_details": PERSONAS[persona],
    }


# ============================================
# FUNCTION 7: Select Interviewer Persona
# ============================================
def select_persona(stress_score: float) -> str:
    """
    Select interviewer persona based on stress score.

    THIS IS THE CORE OF OUR DIFFERENTIATOR:
    The interviewer's personality CHANGES based on
    how stressed the candidate appears to be.

    Score ranges:
    0-3   → Challenger  (confident candidate, push harder)
    4-6   → Neutral     (normal performance, standard interview)
    7-8   → Prober      (some stress, gentle follow-ups)
    9-10  → Supportive  (high stress, encourage and reframe)

    Args:
        stress_score: 0-10 stress score

    Returns:
        Persona key string
    """
    if stress_score <= 3:
        return "challenger"
    elif stress_score <= 6:
        return "neutral"
    elif stress_score <= 8:
        return "prober"
    else:
        return "supportive"


# ============================================
# FUNCTION 8: Get Persona System Prompt
# ============================================
def get_persona_prompt(persona: str) -> str:
    """
    Get the system prompt for a given persona.
    Injected into GPT when generating next question.

    Args:
        persona: "challenger" | "neutral" | "prober" | "supportive"

    Returns:
        System prompt string for GPT
    """
    return PERSONAS.get(persona, PERSONAS["neutral"])["system_prompt"]
