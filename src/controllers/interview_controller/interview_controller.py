"""
Interview Controller
--------------------
Dynamic, LLM-directed interview flow over WebSocket.

REST Endpoints:
  POST /api/v1/interviews                     — Initialise interview, get first question
  GET  /api/v1/interviews/{session_id}/status — Current interview state
  POST /api/v1/interviews/{session_id}/end    — Force-end interview, trigger report

WebSocket:
  WS /api/v1/interviews/{session_id}/stream   — Real-time voice interview loop

WebSocket Protocol
------------------
Client → Server:
  • Binary frames  : raw audio bytes (webm / wav) — accumulated until end-of-speech
  • JSON text frame: {"type": "end_of_speech"}    — client VAD detected 10 s silence
  • JSON text frame: {"type": "ping"}              — keepalive

Server → Client:
  • {"type": "question",  "text": "...", "topic": "...", "question_id": "..."}
  • {"type": "follow_up", "text": "...", "topic": "...", "question_id": "..."}
  • {"type": "complete",  "message": "Interview complete. Report is being generated."}
  • {"type": "error",     "message": "..."}
  • {"type": "pong"}

Silence handling
----------------
If the client does NOT send an end_of_speech signal, a server-side timer will
auto-trigger processing after SILENCE_TIMEOUT_S seconds of receiving no audio.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from src.api.deps import DbSession, RedisClient
from src.config.database import AsyncSessionFactory
from src.config.redis import get_redis_client
from src.config.settings import settings
from src.models.conversation_log import ConversationLog
from src.models.evaluation_result import EvaluationResult
from src.models.interview_record import InterviewRecord
from src.models.interview_session import SessionStatus
from src.repositories.evaluation import EvaluationRepository
from src.repositories.record import RecordRepository
from src.repositories.session import SessionRepository
from src.schemas.interview import InterviewStart
from src.schemas.session import SessionState
from src.services.evaluator import evaluate_answer
from src.services.interview_director import decide_next_action, generate_opening_question
from src.services.session import SessionService
from src.services.speech.stt import transcribe_audio
from src.utils import response as resp
from src.utils.errors import NotFoundError, ValidationError
from src.utils.logger import logger

router = APIRouter(prefix="/interviews", tags=["Interviews"])

# How long (seconds) to wait for audio before auto-triggering processing
SILENCE_TIMEOUT_S: int = 10


# ── REST: Start Interview ────────────────────────────────────────────────────

@router.post(
    "",
    status_code=201,
    summary="Initialise an interview session",
    description=(
        "Links the session to a candidate + job, loads JD/resume context, "
        "and generates the first interview question via the LLM director. "
        "After this call, connect to the WebSocket stream to begin the voice loop."
    ),
)
async def start_interview(
    body: InterviewStart,
    db: DbSession,
    redis: RedisClient,
) -> JSONResponse:
    session_svc = SessionService(db, redis)
    session_repo = SessionRepository(db)

    session = await session_svc.get_session(body.session_id)
    if session.status not in (SessionStatus.INITIALIZED,):
        raise ValidationError(
            f"Session already in '{session.status.value}' — cannot start again"
        )

    # Mark in-progress
    session.status = SessionStatus.IN_PROGRESS
    await session_repo.update(session)

    state = await session_svc.get_session_state(body.session_id)
    state.status = SessionStatus.IN_PROGRESS.value

    # Generate the opening question via LLM director
    result = await generate_opening_question(state)

    question_id = str(uuid.uuid4())
    question_text = result["question_text"]
    topic = result["topic"]

    # Update session state
    state.current_question = {
        "question_id": question_id,
        "text": question_text,
        "topic": topic,
        "skill": topic,
        "difficulty": state.jd_context.get("seniority_level", "intermediate") if state.jd_context else "intermediate",
    }
    state.conversation_history.append(
        {
            "role": "agent",
            "content": question_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    await session_svc.update_session_state(state)

    # Persist conversation log
    db.add(ConversationLog(session_id=body.session_id, role="agent", content=question_text))
    await db.flush()

    return resp.created(
        data={
            "session_id": str(body.session_id),
            "first_question": {
                "question_id": question_id,
                "text": question_text,
                "topic": topic,
            },
            "ws_url": f"/api/v1/interviews/{body.session_id}/stream",
        },
        message="Interview started. Connect to the WebSocket stream to begin.",
    )


# ── REST: Status ─────────────────────────────────────────────────────────────

@router.get(
    "/{session_id}/status",
    summary="Get interview status",
    description="Returns current interview state: status, questions asked, active question.",
)
async def get_interview_status(
    session_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> JSONResponse:
    session_svc = SessionService(db, redis)
    state = await session_svc.get_session_state(session_id)
    session = await session_svc.get_session(session_id)

    return resp.success(
        data={
            "session_id": str(session_id),
            "status": session.status.value,
            "questions_asked": state.questions_asked,
            "max_questions": settings.INTERVIEW_MAX_QUESTIONS,
            "current_question": state.current_question,
        }
    )


# ── REST: Force-End ───────────────────────────────────────────────────────────

@router.post(
    "/{session_id}/end",
    summary="Force-end an interview",
    description="Immediately ends the interview and triggers report generation.",
)
async def end_interview(
    session_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> JSONResponse:
    session_svc = SessionService(db, redis)
    record_repo = RecordRepository(db)

    records = await record_repo.get_by_session_with_evaluations(session_id)
    scores = [r.evaluation.score for r in records if r.evaluation]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    await session_svc.end_session(session_id, total_score=avg_score)

    from src.services.report import ReportService
    try:
        await ReportService(db).generate_report(session_id)
    except Exception as exc:
        logger.error("Report generation failed on force-end: {}", exc)

    return resp.success(message="Interview ended. Report generation has been triggered.")


# ── WebSocket: Real-time Voice Loop ──────────────────────────────────────────

@router.websocket("/{session_id}/stream")
async def interview_stream(session_id: uuid.UUID, websocket: WebSocket) -> None:
    """
    Real-time voice interview WebSocket.

    Audio flow:
      1. Client connects → server confirms session + sends current question as JSON
      2. Client streams binary audio chunks
      3. Client sends {"type": "end_of_speech"} when done speaking
         OR server auto-triggers after SILENCE_TIMEOUT_S of no audio
      4. Server transcribes accumulated audio → LLM director → JSON response
      5. Repeat until action == "end_interview"
    """
    await websocket.accept()
    logger.info("WS connected | session={}", session_id)

    async with AsyncSessionFactory() as db:
        redis = get_redis_client()
        session_svc = SessionService(db, redis)
        record_repo = RecordRepository(db)
        eval_repo = EvaluationRepository(db)

        try:
            # Verify session exists and is in-progress
            try:
                session = await session_svc.get_session(session_id)
            except NotFoundError:
                await _ws_send_error(websocket, "Session not found")
                await websocket.close(code=4004)
                return

            if session.status != SessionStatus.IN_PROGRESS:
                await _ws_send_error(
                    websocket,
                    f"Session is '{session.status.value}'. Call POST /interviews first.",
                )
                await websocket.close(code=4003)
                return

            state = await session_svc.get_session_state(session_id)

            # Send current question to client
            if state.current_question:
                await _ws_send_question(websocket, state.current_question, "question")

            # Main interview loop
            audio_buffer: list[bytes] = []
            last_audio_time: float = asyncio.get_event_loop().time()

            async def _process_audio() -> bool:
                """
                Transcribe buffered audio, run LLM director, persist records.
                Returns True if interview should end.
                """
                nonlocal audio_buffer, state

                if not audio_buffer:
                    logger.debug("WS: process_audio called with empty buffer, skipping")
                    return False

                combined = b"".join(audio_buffer)
                audio_buffer = []

                # Transcribe
                try:
                    transcript = await transcribe_audio(
                        audio_bytes=combined,
                        content_type="audio/webm",
                        filename="candidate_answer.webm",
                    )
                except Exception as exc:
                    logger.error("Transcription error in WS: {}", exc)
                    await _ws_send_error(websocket, "Transcription failed. Please speak again.")
                    return False

                if not transcript.strip():
                    await _ws_send_error(websocket, "No speech detected. Please speak again.")
                    return False

                logger.info("WS transcript | session={} | text={!r}", session_id, transcript[:80])

                # Log candidate answer
                state.conversation_history.append(
                    {
                        "role": "candidate",
                        "content": transcript,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                db.add(ConversationLog(session_id=session_id, role="candidate", content=transcript))

                # Persist interview record
                current_q = state.current_question or {}
                record = InterviewRecord(
                    session_id=session_id,
                    question_id=current_q.get("question_id", str(uuid.uuid4())),
                    question_text=current_q.get("text", ""),
                    question_skill=current_q.get("skill", "general"),
                    question_difficulty=current_q.get("difficulty", "intermediate"),
                    candidate_answer=transcript,
                )
                record = await record_repo.create(record)

                # Evaluate answer
                try:
                    evaluation = await evaluate_answer(
                        question_text=current_q.get("text", ""),
                        candidate_answer=transcript,
                        question_skill=current_q.get("skill", "general"),
                        question_difficulty=current_q.get("difficulty", "intermediate"),
                        jd_context=state.jd_context,
                    )
                    eval_result = EvaluationResult(
                        record_id=record.id,
                        score=evaluation.score,
                        feedback=evaluation.feedback,
                        strengths=evaluation.strengths,
                        weaknesses=evaluation.weaknesses,
                    )
                    db.add(eval_result)
                except Exception as exc:
                    logger.warning("Evaluation failed (non-fatal): {}", exc)

                state.questions_asked += 1
                await db.flush()

                # LLM director decides next action
                decision = await decide_next_action(
                    state=state,
                    latest_transcript=transcript,
                    max_questions=settings.INTERVIEW_MAX_QUESTIONS,
                )

                action = decision["action"]
                question_text = decision.get("question_text", "")
                topic = decision.get("topic", "general")

                if action == "end_interview":
                    state.status = SessionStatus.COMPLETED.value
                    state.current_question = None
                    await session_svc.update_session_state(state)
                    await _finalize(session_id, db, session_svc, record_repo)
                    await websocket.send_text(
                        json.dumps({"type": "complete", "message": "Interview complete. Thank you!"})
                    )
                    return True

                # next_question or follow_up
                question_id = str(uuid.uuid4())
                state.current_question = {
                    "question_id": question_id,
                    "text": question_text,
                    "topic": topic,
                    "skill": topic,
                    "difficulty": current_q.get("difficulty", "intermediate"),
                }
                state.conversation_history.append(
                    {
                        "role": "agent",
                        "content": question_text,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                await session_svc.update_session_state(state)
                db.add(ConversationLog(session_id=session_id, role="agent", content=question_text))
                await db.flush()

                await _ws_send_question(
                    websocket,
                    state.current_question,
                    msg_type="follow_up" if action == "follow_up" else "question",
                )
                return False

            # ── Receive loop ────────────────────────────────────────────────
            silence_task: asyncio.Task | None = None

            async def _silence_watchdog() -> None:
                """Auto-trigger processing after SILENCE_TIMEOUT_S with no audio."""
                await asyncio.sleep(SILENCE_TIMEOUT_S)
                if audio_buffer:
                    logger.info("WS silence timeout triggered | session={}", session_id)
                    should_end = await _process_audio()
                    if should_end:
                        await websocket.close(code=1000)

            while True:
                try:
                    # Use a short receive timeout so we can check the silence timer
                    message = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=SILENCE_TIMEOUT_S + 1,
                    )
                except asyncio.TimeoutError:
                    # Nothing received — check if we have buffered audio to process
                    if audio_buffer:
                        should_end = await _process_audio()
                        if should_end:
                            break
                    continue
                except WebSocketDisconnect:
                    logger.info("WS disconnected | session={}", session_id)
                    break

                # Handle disconnect notification from FastAPI
                if message.get("type") == "websocket.disconnect":
                    logger.info("WS disconnect message | session={}", session_id)
                    break

                # Binary audio frame
                if "bytes" in message and message["bytes"] is not None:
                    audio_buffer.append(message["bytes"])
                    last_audio_time = asyncio.get_event_loop().time()
                    # Cancel existing silence watchdog and restart
                    if silence_task and not silence_task.done():
                        silence_task.cancel()
                    silence_task = asyncio.create_task(_silence_watchdog())
                    continue

                # Text JSON frame
                if "text" in message and message["text"] is not None:
                    try:
                        msg = json.loads(message["text"])
                    except json.JSONDecodeError:
                        continue

                    msg_type = msg.get("type", "")

                    if msg_type == "end_of_speech":
                        if silence_task and not silence_task.done():
                            silence_task.cancel()
                        should_end = await _process_audio()
                        if should_end:
                            break

                    elif msg_type == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))

        except WebSocketDisconnect:
            logger.info("WS client disconnected | session={}", session_id)
        except Exception as exc:
            logger.error("WS unexpected error | session={} | err={}", session_id, exc)
            try:
                await _ws_send_error(websocket, "An internal error occurred.")
                await websocket.close(code=1011)
            except Exception:
                pass


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _ws_send_question(websocket: WebSocket, question: dict, msg_type: str = "question") -> None:
    await websocket.send_text(
        json.dumps(
            {
                "type": msg_type,
                "question_id": question.get("question_id", ""),
                "text": question.get("text", ""),
                "topic": question.get("topic", question.get("skill", "")),
            }
        )
    )


async def _ws_send_error(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_text(json.dumps({"type": "error", "message": message}))
    except Exception:
        pass


async def _finalize(session_id, db, session_svc, record_repo) -> None:
    """Compute average score, end session, generate report."""
    from src.services.report import ReportService

    records = await record_repo.get_by_session_with_evaluations(session_id)
    scores = [r.evaluation.score for r in records if r.evaluation]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    await session_svc.end_session(session_id, total_score=avg_score)
    try:
        await ReportService(db).generate_report(session_id)
    except Exception as exc:
        logger.error("Report generation failed: {}", exc)
