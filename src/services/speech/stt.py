from __future__ import annotations

import io
from typing import Optional

from openai import AsyncOpenAI

from src.config.settings import settings
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger

_openai_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


async def transcribe_audio(
    audio_bytes: bytes,
    content_type: str = "audio/webm",
    filename: str = "audio.webm",
) -> str:
    """Transcribe audio bytes to text using OpenAI Whisper."""
    client = get_openai_client()

    # Map content_type to file extension
    ext_map = {
        "audio/webm": "webm",
        "audio/wav": "wav",
        "audio/wave": "wav",
        "audio/mp3": "mp3",
        "audio/mpeg": "mp3",
        "audio/mp4": "mp4",
        "audio/ogg": "ogg",
        "audio/flac": "flac",
        "audio/m4a": "m4a",
    }
    ext = ext_map.get(content_type.lower(), "webm")
    fname = f"audio.{ext}"

    logger.debug("Transcribing audio | size={size} bytes | type={type}", size=len(audio_bytes), type=content_type)

    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = fname

        response = await client.audio.transcriptions.create(
            model=settings.WHISPER_MODEL,
            file=(fname, audio_bytes, content_type),
            response_format="text",
        )
        transcript = response if isinstance(response, str) else str(response)
        logger.info("Transcription complete | length={length}", length=len(transcript))
        return transcript.strip()
    except Exception as exc:
        logger.error("STT error: {error}", error=str(exc))
        raise ExternalServiceError(f"Speech-to-text failed: {exc}") from exc
