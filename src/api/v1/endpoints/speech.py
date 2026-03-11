from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse, Response

from src.api.deps import DbSession
from src.config.settings import settings
from src.schemas.speech import SynthesizeRequest, SynthesizeResponse, TranscribeResponse
from src.services.speech.stt import transcribe_audio
from src.services.speech.tts import synthesize_speech
from src.utils import response as resp
from src.utils.errors import ValidationError
from src.utils.logger import logger

router = APIRouter(prefix="/speech", tags=["speech"])

ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/wave",
    "audio/mp3",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "audio/flac",
    "audio/m4a",
}


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...)) -> JSONResponse:
    """Upload an audio file and return its transcript via Whisper STT."""
    content_type = file.content_type or "audio/webm"

    if content_type not in ALLOWED_AUDIO_TYPES:
        raise ValidationError(
            f"Unsupported audio format '{content_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_AUDIO_TYPES))}"
        )

    max_bytes = settings.MAX_AUDIO_FILE_SIZE_MB * 1024 * 1024
    audio_bytes = await file.read()

    if len(audio_bytes) > max_bytes:
        raise ValidationError(
            f"File too large. Maximum size is {settings.MAX_AUDIO_FILE_SIZE_MB} MB"
        )

    if not audio_bytes:
        raise ValidationError("Uploaded file is empty")

    logger.info(
        "Transcribing audio | filename={name} | size={size} bytes",
        name=file.filename,
        size=len(audio_bytes),
    )

    transcript = await transcribe_audio(
        audio_bytes=audio_bytes,
        content_type=content_type,
        filename=file.filename or "audio.webm",
    )

    result = TranscribeResponse(transcript=transcript)
    return resp.success(
        data=result.model_dump(),
        message="Audio transcribed successfully",
    )


@router.post("/synthesize")
async def synthesize(body: SynthesizeRequest) -> Response:
    """Convert text to speech and return audio bytes (MP3)."""
    logger.info("Synthesizing speech | chars={chars}", chars=len(body.text))

    audio_bytes = await synthesize_speech(
        text=body.text,
        voice_id=body.voice_id,
        model_id=body.model_id,
    )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": "attachment; filename=speech.mp3",
            "Content-Length": str(len(audio_bytes)),
            "X-Audio-Size": str(len(audio_bytes)),
        },
    )
