# Voice-Agent Project Memory

## Project
Voice-Based Interview Agent — Python FastAPI backend at:
`C:\Users\admin\Desktop\Voice Agent\Voice-agent`

## Stack
- FastAPI + uvicorn (async)
- SQLAlchemy 2.x async + Alembic + PostgreSQL (asyncpg)
- redis-py async (session caching)
- anthropic SDK (Claude — question gen, evaluation, report)
- openai SDK (Whisper STT)
- elevenlabs SDK (TTS)
- pydantic-settings (config)
- loguru (logging)

## Architecture
Controller → Service → Repository (strict separation)
- `src/api/v1/endpoints/` — HTTP layer only
- `src/services/` — business logic
- `src/repositories/` — all DB access
- `src/models/` — SQLAlchemy ORM
- `src/schemas/` — Pydantic request/response
- `src/config/` — settings, database, redis singletons

## Key Design Decisions
- **Prototype mode** — no JWT auth, no rate limiting, all endpoints open
- CORS: allow all origins (`["*"]`)
- Only `DATABASE_URL` and `ANTHROPIC_API_KEY` are required env vars
- `OPENAI_API_KEY`, `ELEVENLABS_*` are optional (default `""`)
- `main.py` uses `lifespan` context manager (NOT deprecated `@app.on_event`)
- `src/api/deps.py` only has `DbSession` and `RedisClient` — no auth dependency
- Redis used as cache-aside for session state (TTL = REDIS_SESSION_TTL_SECONDS)

## User Preferences
- Keep it simple / prototype first — no production overhead
- Python backend only (no Node/TypeScript)

## Entry Point
`python main.py` or `uvicorn main:app --reload`

## To Get Started
1. Copy `.env.example` to `.env`, fill in DATABASE_URL and ANTHROPIC_API_KEY
2. `docker compose up -d` (starts PostgreSQL + Redis)
3. `pip install -r requirements.txt`
4. `alembic upgrade head`
5. `python main.py`