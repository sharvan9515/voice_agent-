"""
Speech Controller
-----------------
Handles all voice I/O for the interview pipeline.

Routes:
  POST /api/v1/speech/transcribe   — Candidate audio → text  (Speech Input)
  POST /api/v1/speech/synthesize   — LLM text → audio        (LLM Speech Output)
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.services.speech.stt import transcribe_audio
from src.services.speech.tts import synthesize_speech
from src.utils import response as resp
from src.utils.errors import ValidationError
from src.utils.logger import logger

router = APIRouter(prefix="/speech", tags=["Speech"])

ALLOWED_AUDIO_TYPES = {
    "audio/webm", "audio/wav", "audio/wave",
    "audio/mp3", "audio/mpeg", "audio/mp4",
    "audio/ogg", "audio/flac", "audio/m4a",
}


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="Text to convert to speech")
    voice: Optional[Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"]] = Field(
        None, description="OpenAI TTS voice. Defaults to the configured default."
    )
    model: Optional[Literal["tts-1", "tts-1-hd"]] = Field(
        None, description="TTS model. tts-1 is faster, tts-1-hd is higher quality."
    )


# ── Speech Input (Candidate → System) ─────────────────────────────────────────

@router.post(
    "/transcribe",
    summary="Transcribe candidate speech to text",
    description="Upload an audio recording of the candidate's answer. "
                "The audio is transcribed using OpenAI Whisper and returned as plain text, "
                "ready to be submitted to the interview pipeline.",
)
async def transcribe_candidate_speech(
    file: UploadFile = File(..., description="Audio file (webm, wav, mp3, mp4, ogg, flac, m4a)"),
) -> JSONResponse:
    content_type = file.content_type or "audio/webm"

    if content_type not in ALLOWED_AUDIO_TYPES:
        raise ValidationError(
            f"Unsupported audio format '{content_type}'. "
            f"Supported formats: {', '.join(sorted(ALLOWED_AUDIO_TYPES))}"
        )

    audio_bytes = await file.read()
    max_bytes = settings.MAX_AUDIO_FILE_SIZE_MB * 1024 * 1024

    if not audio_bytes:
        raise ValidationError("Uploaded audio file is empty")
    if len(audio_bytes) > max_bytes:
        raise ValidationError(f"File exceeds maximum allowed size of {settings.MAX_AUDIO_FILE_SIZE_MB} MB")

    logger.info("Transcribing candidate audio | filename={} | size={} bytes", file.filename, len(audio_bytes))

    transcript = await transcribe_audio(
        audio_bytes=audio_bytes,
        content_type=content_type,
        filename=file.filename or "audio.webm",
    )

    return resp.success(
        data={"transcript": transcript, "character_count": len(transcript)},
        message="Audio transcribed successfully",
    )


# ── LLM Speech Output (System → Candidate) ────────────────────────────────────

@router.post(
    "/synthesize",
    summary="Synthesize LLM response to speech",
    description="Convert a text string (typically an LLM-generated interview question or response) "
                "into an audio file using OpenAI TTS. Returns MP3 audio bytes suitable for "
                "playback directly in the browser or mobile client.",
    response_class=Response,
    responses={
        200: {
            "content": {"audio/mpeg": {}},
            "description": "MP3 audio of the synthesized speech",
        }
    },
)
async def synthesize_llm_speech(body: SynthesizeRequest) -> Response:
    logger.info("Synthesizing LLM speech | chars={} | voice={}", len(body.text), body.voice)

    audio_bytes = await synthesize_speech(
        text=body.text,
        voice=body.voice,
        model=body.model,
    )

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": 'attachment; filename="llm_response.mp3"',
            "Content-Length": str(len(audio_bytes)),
            "X-Character-Count": str(len(body.text)),
        },
    )
