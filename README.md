# Voice Interview Agent

A full-stack AI-powered voice interview system. Upload a job description and candidate resume, then conduct a fully automated voice interview — the AI asks tailored questions, listens to answers in real time, and generates a detailed evaluation report.

---

## How It Works

```
1. Upload JD PDF + Candidate Resume
           ↓
2. AI parses both → builds interview context (matched skills, gaps)
           ↓
3. GPT-4o generates the first tailored question → played via TTS
           ↓
4. Candidate speaks → audio streamed to backend → Whisper transcribes
           ↓
5. LLM Director decides: follow_up / next_question / end_interview
           ↓
6. Repeat until done → Evaluation report generated
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11 · FastAPI · Uvicorn |
| **LLM** | OpenAI GPT-4o |
| **Speech-to-Text** | OpenAI Whisper (`whisper-1`) |
| **Text-to-Speech** | OpenAI TTS (`tts-1`) |
| **Database** | PostgreSQL 15 (SQLAlchemy async + asyncpg) |
| **Cache / Sessions** | Redis 7 |
| **Migrations** | Alembic |
| **PDF Parsing** | pdfplumber |
| **Frontend** | React 18 · TypeScript · Vite · Tailwind CSS |
| **Real-time** | WebSocket (FastAPI native) |
| **Infrastructure** | Docker Compose |

---

## Project Structure

```
Voice-agent/
├── main.py                          # FastAPI app entry point
├── requirements.txt
├── docker-compose.yml               # PostgreSQL + Redis
├── .env                             # Environment variables (not committed)
│
├── alembic/                         # Database migrations
│   └── versions/
│
├── src/
│   ├── config/
│   │   ├── settings.py              # Env var validation (pydantic-settings)
│   │   ├── database.py              # SQLAlchemy async engine + session factory
│   │   ├── redis.py                 # Redis client singleton
│   │   └── openai_client.py         # Shared OpenAI client + chat_json() helper
│   │
│   ├── models/                      # SQLAlchemy ORM models
│   │   ├── candidate.py
│   │   ├── job.py
│   │   ├── interview_session.py
│   │   ├── interview_record.py
│   │   ├── evaluation_result.py
│   │   ├── conversation_log.py
│   │   └── interview_report.py
│   │
│   ├── repositories/                # DB access layer (one per model)
│   │   ├── candidate.py
│   │   ├── session.py
│   │   ├── record.py
│   │   ├── evaluation.py
│   │   └── report.py
│   │
│   ├── services/
│   │   ├── interview_director.py    # LLM decides: follow_up / next / end
│   │   ├── question.py              # GPT-4o question generation
│   │   ├── evaluator.py             # GPT-4o answer evaluation (score 0–10)
│   │   ├── interview.py             # Interview lifecycle orchestration
│   │   ├── session.py               # Redis session state management
│   │   ├── job.py                   # Job description CRUD
│   │   ├── candidate.py             # Candidate CRUD
│   │   ├── report.py                # Report generation & export
│   │   ├── parsers/
│   │   │   ├── jd_parser.py         # JD PDF → structured ParsedJD
│   │   │   ├── resume_parser.py     # Resume PDF → structured ParsedResume
│   │   │   ├── context_builder.py   # Merges JD + Resume → InterviewContext
│   │   │   └── pdf_extractor.py     # pdfplumber text extraction
│   │   └── speech/
│   │       ├── stt.py               # Whisper transcription
│   │       └── tts.py               # OpenAI TTS synthesis
│   │
│   ├── controllers/                 # HTTP layer (one folder per domain)
│   │   ├── interview_controller/    # REST + WebSocket interview endpoints
│   │   ├── document_controller/     # JD and resume upload
│   │   ├── speech_controller/       # Transcribe + synthesize
│   │   ├── session_controller/
│   │   ├── candidate_controller/
│   │   └── report_controller/
│   │
│   ├── schemas/                     # Pydantic request/response schemas
│   ├── middleware/                  # Error handler
│   └── utils/
│       ├── logger.py                # Loguru logger
│       ├── errors.py                # Custom exception classes
│       └── response.py              # Standardised API response helpers
│
└── frontend/                        # React single-page app
    ├── src/
    │   ├── App.tsx                  # State machine: setup → interview → report
    │   ├── api/client.ts            # All fetch calls to the backend
    │   ├── hooks/
    │   │   ├── useAudioRecorder.ts  # MediaRecorder + Web Audio VAD
    │   │   └── useInterviewSocket.ts # WebSocket lifecycle
    │   └── components/
    │       ├── SetupForm.tsx        # Upload JD + resume, create session
    │       ├── InterviewRoom.tsx    # Live voice interview room
    │       └── ReportView.tsx       # Score + strengths/weaknesses report
    ├── vite.config.ts               # Proxy /api → localhost:8000
    └── tailwind.config.js
```

---

## Quick Start

### 1. Prerequisites

- Docker Desktop running
- Python 3.11+
- Node.js 18+
- OpenAI API key

### 2. Start infrastructure

```bash
docker-compose up -d
# PostgreSQL → localhost:5433
# Redis     → localhost:6379
```

### 3. Backend

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5433/voice_agent
REDIS_URL=redis://localhost:6379
OPENAI_API_KEY=sk-...
```

Run database migrations:

```bash
alembic upgrade head
```

Start the server:

```bash
uvicorn main:app --reload --port 8000
```

Interactive API docs: **http://localhost:8000/docs**

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Vite proxies all `/api` calls to the backend automatically — no CORS config needed.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL async connection string |
| `REDIS_URL` | | `redis://localhost:6379` | Redis connection string |
| `OPENAI_API_KEY` | ✅ | — | Used for GPT-4o, Whisper, and TTS |
| `OPENAI_MODEL` | | `gpt-4o` | Chat model |
| `WHISPER_MODEL` | | `whisper-1` | Speech-to-text model |
| `OPENAI_TTS_MODEL` | | `tts-1` | TTS model (`tts-1` or `tts-1-hd`) |
| `OPENAI_TTS_VOICE` | | `alloy` | TTS voice (`alloy`, `echo`, `nova`, etc.) |
| `INTERVIEW_MAX_QUESTIONS` | | `10` | Max questions per session |
| `MAX_AUDIO_FILE_SIZE_MB` | | `25` | Max upload size for audio |
| `PORT` | | `8000` | Server port |
| `APP_ENV` | | `development` | `development` or `production` |

---

## API Reference

Base path: `/api/v1`

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/documents/job-description/upload` | Upload JD as PDF — parsed by GPT-4o |
| `POST` | `/documents/job-description` | Create JD from plain text |
| `GET` | `/documents/job-description/{job_id}` | Retrieve parsed JD |
| `POST` | `/documents/resume/{candidate_id}` | Upload resume PDF — parsed by GPT-4o |

### Candidates
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/candidates` | Create candidate profile |
| `GET` | `/candidates/{id}` | Get candidate |
| `PUT` | `/candidates/{id}` | Update candidate |

### Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions` | Create interview session (links candidate + job) |
| `GET` | `/sessions/{id}` | Get session state from Redis cache |
| `DELETE` | `/sessions/{id}` | Abort session |

### Interviews
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/interviews` | Start interview — generates first question |
| `GET` | `/interviews/{session_id}/status` | Current interview state |
| `POST` | `/interviews/{session_id}/end` | Force-end — triggers report generation |
| **`WS`** | `/interviews/{session_id}/stream` | **Real-time voice interview loop** |

### Speech
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/speech/transcribe` | Upload audio file → transcript text (Whisper) |
| `POST` | `/speech/synthesize` | Text → MP3 audio (OpenAI TTS) |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/reports/{session_id}` | Get generated report |
| `POST` | `/reports/{session_id}/generate` | Manually trigger report generation |
| `GET` | `/reports/{report_id}/export` | Export report as JSON |

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | DB + Redis liveness check |

---

## WebSocket Protocol

**Connect:** `WS /api/v1/interviews/{session_id}/stream`

**Client → Server**

| Frame type | Content | Meaning |
|------------|---------|---------|
| Binary | Raw audio bytes (WebM/WAV) | Streaming mic audio while candidate speaks |
| Text | `{"type": "end_of_speech"}` | Candidate finished — process answer now |
| Text | `{"type": "ping"}` | Keepalive |

**Server → Client**

| `type` | Payload fields | Meaning |
|--------|----------------|---------|
| `question` | `text`, `topic`, `question_id` | New question (next topic) |
| `follow_up` | `text`, `topic`, `question_id` | Probing deeper on same topic |
| `complete` | `message` | Interview done — report is generating |
| `error` | `message` | Non-fatal error — stay in recording state |
| `pong` | — | Keepalive response |

> **10-second silence auto-trigger:** the server processes buffered audio automatically after 10 s of no incoming audio frames. The client can also send `end_of_speech` at any time to trigger immediately.

---

## LLM Director

`src/services/interview_director.py` drives the dynamic interview flow.

After each candidate answer, GPT-4o receives:
- Last 10 turns of conversation history
- JD context: role, domain, required skills, candidate skills, skill gaps
- Number of questions asked vs. the configured maximum

It returns one of three actions:

| Action | When used |
|--------|-----------|
| `follow_up` | Answer was vague, incomplete, or off-topic — probe deeper |
| `next_question` | Answer was sufficient — move to the next topic |
| `end_interview` | All key areas covered, or question limit reached |

---

## Database Schema

```
candidates          — id, name, email, experience_level, resume_parsed (JSON)
jobs                — id, title, company, description_raw, description_parsed (JSON)
interview_sessions  — id, candidate_id, job_id, status, total_score, started_at, ended_at
interview_records   — id, session_id, question_text, candidate_answer, skill, difficulty
evaluation_results  — id, record_id, score (0–10), feedback, strengths[], weaknesses[]
conversation_logs   — id, session_id, role (agent|candidate), content, timestamp
interview_reports   — id, session_id, total_score, summary, strengths[], weaknesses[]
```

---

## Frontend UI Flow

The React app is a single page with three sequential states:

```
SetupForm  →  InterviewRoom  →  ReportView
```

**SetupForm**
- Enter job title + optional company name
- Upload JD PDF (parsed server-side by GPT-4o)
- Enter candidate name + email + experience level
- Upload resume PDF (parsed server-side by GPT-4o)
- All setup steps shown with live progress indicators

**InterviewRoom**
- WebSocket connects on mount — server sends first question immediately
- Question text is synthesized via TTS and auto-played
- Mic unlocks after agent finishes speaking
- `MediaRecorder` streams binary audio chunks to WebSocket every 200 ms
- `AnalyserNode` (Web Audio API) monitors mic RMS energy for silence detection
- After 10 seconds of silence, or clicking the mic button, `end_of_speech` is sent
- Server transcribes → LLM director → next question / follow-up / complete
- Conversation history shown in a chat-style view

**ReportView**
- Polls `GET /reports/{session_id}` with retry (report generation is async)
- Animated score ring (0–10)
- Strengths and areas for improvement panels
- Summary paragraph from GPT-4o
- Export report as JSON button
