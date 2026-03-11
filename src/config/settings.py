from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import json
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    APP_ENV: str = "development"
    PORT: int = 8000
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_SESSION_TTL_SECONDS: int = 7200

    # OpenAI — LLM + STT (Whisper) + TTS (single key for everything)
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_MAX_TOKENS: int = 2048
    WHISPER_MODEL: str = "whisper-1"
    OPENAI_TTS_MODEL: str = "tts-1"
    OPENAI_TTS_VOICE: str = "alloy"  # alloy | echo | fable | onyx | nova | shimmer

    INTERVIEW_MAX_QUESTIONS: int = 10
    INTERVIEW_DEFAULT_SKILL: str = "general"
    INTERVIEW_DEFAULT_DIFFICULTY: str = "intermediate"

    UPLOAD_DIR: str = "./uploads"
    MAX_AUDIO_FILE_SIZE_MB: int = 25
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"

    CORS_ORIGINS: List[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [o.strip() for o in v.split(",")]
        return v


settings = Settings()
