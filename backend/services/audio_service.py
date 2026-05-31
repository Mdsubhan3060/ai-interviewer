# ============================================
# services/audio_service.py
# ============================================
# WHY THIS FILE EXISTS:
# Handles audio file processing for the mock interview.
# When user speaks their answer, this file:
#   1. Validates the audio file
#   2. Compresses it (Whisper has 25MB limit)
#   3. Transcribes speech to text using Whisper
#   4. Returns the text + duration info
#
# WHAT IS WHISPER?
# Whisper is OpenAI's speech-to-text model.
# It runs LOCALLY on your machine — no API call needed.
# It was downloaded when you ran: pip install openai-whisper
#
# It supports: mp3, mp4, wav, m4a, webm, ogg
# Accuracy is very high — better than most cloud APIs.
# It even handles accents well.
#
# WHY COMPRESSION?
# Whisper's hard limit = 25MB per file.
# A 5-minute WAV recording = ~50MB (too big).
# We convert to mp3 at 64kbps:
#   5 minutes → ~2.4MB (safely under limit).
# ============================================

import io
import logging
import os
import tempfile
import time
from pathlib import Path

import whisper
from pydub import AudioSegment

logger = logging.getLogger(__name__)

# ============================================
# Load Whisper Model Once
# ============================================
# Just like HuggingFace in resume_service.py,
# we load Whisper ONCE at startup.
#
# Model sizes and tradeoffs:
#   tiny   → fastest, least accurate (~1GB RAM)
#   base   → good balance (we use this) (~1GB RAM)
#   small  → better accuracy (~2GB RAM)
#   medium → even better (~5GB RAM)
#   large  → best accuracy (~10GB RAM)
#
# "base" is perfect for interview answers:
# - Fast enough for real-time feel
# - Accurate enough for clear speech
# ============================================
logger.info("Loading Whisper model (base)...")
try:
    whisper_model = whisper.load_model("base")
    logger.info("✅ Whisper model loaded")
except Exception as e:
    logger.error(f"Failed to load Whisper: {e}")
    whisper_model = None


# ============================================
# FUNCTION 1: Validate Audio File
# ============================================
def validate_audio(
    file_bytes: bytes,
    filename: str,
    max_size_mb: int = 25,
) -> None:
    """
    Validate audio file before processing.

    Checks:
    - File is not empty
    - File extension is supported
    - File size is under limit

    Raises ValueError if validation fails.
    """
    # Check not empty
    if not file_bytes or len(file_bytes) == 0:
        raise ValueError("Audio file is empty.")

    # Check extension
    supported = {".mp3", ".mp4", ".wav", ".m4a", ".webm", ".ogg", ".flac"}
    ext = Path(filename).suffix.lower()
    if ext not in supported:
        raise ValueError(
            f"Unsupported audio format: {ext}. "
            f"Supported formats: {', '.join(supported)}"
        )

    # Check size
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(
            f"Audio file too large: {size_mb:.1f}MB. "
            f"Maximum: {max_size_mb}MB. "
            "Please record a shorter answer."
        )


# ============================================
# FUNCTION 2: Compress Audio
# ============================================
def compress_audio(file_bytes: bytes, filename: str) -> bytes:
    """
    Compress audio to mp3 at 64kbps.

    WHY 64kbps?
    - Voice (not music) is clear at 64kbps
    - 5 min audio = ~2.4MB (well under 25MB limit)
    - Whisper accuracy is not affected by this compression

    Args:
        file_bytes: Raw audio bytes
        filename: Original filename (to detect format)

    Returns:
        Compressed mp3 bytes
    """
    try:
        ext = Path(filename).suffix.lower().replace(".", "")
        if ext == "mp4":
            ext = "mp4"  # pydub handles mp4 audio

        # Load audio using pydub
        audio = AudioSegment.from_file(
            io.BytesIO(file_bytes),
            format=ext if ext != "m4a" else "mp4",
        )

        # Export as mp3 at 64kbps
        output = io.BytesIO()
        audio.export(output, format="mp3", bitrate="64k")
        compressed = output.getvalue()

        original_mb = len(file_bytes) / (1024 * 1024)
        compressed_mb = len(compressed) / (1024 * 1024)
        logger.info(
            f"Audio compressed: {original_mb:.1f}MB → {compressed_mb:.1f}MB"
        )

        return compressed

    except Exception as e:
        logger.warning(f"Compression failed, using original: {e}")
        return file_bytes  # fallback to original


# ============================================
# FUNCTION 3: Transcribe Audio With Whisper
# ============================================
def transcribe_audio(file_bytes: bytes) -> dict:
    """
    Transcribe audio bytes to text using Whisper.

    WHY TEMP FILE?
    Whisper needs a file path, not bytes directly.
    We write bytes to a temporary file,
    Whisper reads it, then we delete the temp file.
    The 'with tempfile' pattern handles deletion automatically.

    Args:
        file_bytes: Audio bytes (preferably compressed mp3)

    Returns:
        Dict with:
            text: transcribed text
            duration: audio duration in seconds
            language: detected language
    """
    if whisper_model is None:
        raise RuntimeError(
            "Whisper model not loaded. "
            "Run: pip install openai-whisper"
        )

    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        start_time = time.time()

        # Transcribe
        result = whisper_model.transcribe(
            tmp_path,
            language="en",          # Force English (faster than auto-detect)
            fp16=False,             # Use fp32 (safer on CPU)
            verbose=False,          # Don't print progress to console
        )

        transcription_time = time.time() - start_time
        logger.info(
            f"Transcribed in {transcription_time:.1f}s: "
            f"'{result['text'][:50]}...'"
        )

        return {
            "text": result["text"].strip(),
            "language": result.get("language", "en"),
            "duration": sum(
                seg.get("end", 0) - seg.get("start", 0)
                for seg in result.get("segments", [])
            ),
        }

    finally:
        # Always delete temp file even if transcription fails
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ============================================
# FUNCTION 4: Full Audio Processing Pipeline
# ============================================
async def process_audio_answer(
    file_bytes: bytes,
    filename: str,
) -> dict:
    """
    Complete pipeline: validate → compress → transcribe.

    This is the only function called from outside this file.
    Everything else is internal helpers.

    Args:
        file_bytes: Raw uploaded audio bytes
        filename: Original filename

    Returns:
        Dict with transcribed text + metadata
    """
    # Step 1: Validate
    validate_audio(file_bytes, filename)

    # Step 2: Compress (only if needed)
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > 5:  # Compress if over 5MB
        logger.info(f"Compressing {size_mb:.1f}MB audio file...")
        file_bytes = compress_audio(file_bytes, filename)

    # Step 3: Transcribe
    result = transcribe_audio(file_bytes)

    if not result["text"]:
        raise ValueError(
            "Could not transcribe audio. "
            "Please check your microphone and try again."
        )

    return result
