from __future__ import annotations

from typing import Literal, Optional

from src.config.settings import settings
from src.services.speech.stt import get_openai_client
from src.utils.errors import ExternalServiceError
from src.utils.logger import logger

OpenAIVoice = Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
OpenAITTSModel = Literal["tts-1", "tts-1-hd"]


async def synthesize_speech(
    text: str,
    voice: Optional[OpenAIVoice] = None,
    model: Optional[OpenAITTSModel] = None,
) -> bytes:
    """Convert text to speech using OpenAI TTS and return MP3 bytes."""
    client = get_openai_client()
    effective_voice: OpenAIVoice = voice or settings.OPENAI_TTS_VOICE  # type: ignore[assignment]
    effective_model: OpenAITTSModel = model or settings.OPENAI_TTS_MODEL  # type: ignore[assignment]

    logger.debug(
        "Synthesizing speech | voice={voice} | model={model} | chars={chars}",
        voice=effective_voice,
        model=effective_model,
        chars=len(text),
    )

    try:
        response = await client.audio.speech.create(
            model=effective_model,
            voice=effective_voice,
            input=text,
            response_format="mp3",
        )
        audio_bytes = response.content
        logger.info("TTS complete | size={size} bytes", size=len(audio_bytes))
        return audio_bytes
    except Exception as exc:
        logger.error("TTS error: {error}", error=str(exc))
        raise ExternalServiceError(f"Text-to-speech failed: {exc}") from exc