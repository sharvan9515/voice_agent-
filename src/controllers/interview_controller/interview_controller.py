"""
Interview Controller
--------------------
Multi-agent interview flow via OpenAI Realtime API.

REST Endpoints:
  POST /api/v1/interview                          — Upload resume + JD → screening + session + first question
  POST /api/v1/interview/{session_id}/answer       — Text answer fallback (no-mic users)
  POST /api/v1/interview/{session_id}/end          — Force-end interview, trigger report

WebSocket:
  WS /api/v1/interview/{session_id}/realtime       — Real-time voice interview via OpenAI Realtime API

WebSocket Protocol
------------------
Client → Server (JSON text frames):
  {"type": "audio", "audio": "<base64 PCM16 24kHz mono>"}
  {"type": "commit_audio"}  — manual end-of-speech (VAD handles this automatically)
  {"type": "ping"}

Server → Client (JSON text frames):
  {"type": "session_ready"}
  {"type": "audio", "audio": "<base64 PCM16 24kHz mono>"}
  {"type": "assistant_transcript_delta", "delta": "..."}
  {"type": "assistant_transcript", "text": "..."}
  {"type": "user_transcript", "text": "..."}
  {"type": "speech_started"}
  {"type": "speech_stopped"}
  {"type": "evaluation", "score": N, "skill": "..."}
  {"type": "interview_complete", "message": "..."}
  {"type": "error", "message": "..."}
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from src.api.deps import DbSession, RedisClient
from src.config.database import AsyncSessionFactory
from src.config.redis import get_redis_client
from src.models.conversation_log import ConversationLog
from src.models.evaluation_result import EvaluationResult
from src.models.interview_record import InterviewRecord
from src.models.interview_session import SessionStatus
from src.repositories.evaluation import EvaluationRepository
from src.repositories.record import RecordRepository
from src.schemas.interview_config import InterviewConfig
from src.services.session import SessionService
from src.utils import response as resp
from src.utils.errors import NotFoundError
from src.utils.logger import logger

router = APIRouter(tags=["Interview"])


# ── REST: One-Shot Interview Setup ─────────────────────────────────────────

@router.post(
    "/interview",
    status_code=201,
    summary="One-shot interview setup",
    description=(
        "Upload a resume + JD text → parse both, screen the candidate, "
        "create session, generate the first question. Single call replaces "
        "the multi-step candidate → JD → session → start flow."
    ),
)
async def setup_interview(
    db: DbSession,
    redis: RedisClient,
    file: UploadFile = File(...),
    jd_text: str = Form(""),
    config: str = Form("{}"),
) -> JSONResponse:
    from src.agents.orchestrator import InterviewOrchestrator

    # Detect PDF
    ct = (file.content_type or "").lower()
    filename = (file.filename or "").lower()
    if "pdf" not in ct and filename.endswith(".pdf"):
        ct = "application/pdf"
    if not ct:
        ct = "text/plain"

    # Parse config JSON
    try:
        config_dict = json.loads(config) if config else {}
    except json.JSONDecodeError:
        config_dict = {}

    orchestrator = InterviewOrchestrator(db, redis)
    result = await orchestrator.setup_interview(
        file_bytes=await file.read(),
        content_type=ct,
        jd_text=jd_text.strip(),
        config_dict=config_dict,
    )

    if result.get("status") == "screened_out":
        return resp.success(data=result, message="Candidate did not meet screening threshold.")

    return resp.created(
        data=result,
        message="Interview ready. Connect to the WebSocket stream to begin.",
    )


# ── REST: Text Answer Fallback ─────────────────────────────────────────────

@router.post(
    "/interview/{session_id}/answer",
    summary="Submit a text answer (fallback for no-mic users)",
)
async def submit_text_answer(
    session_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
    answer: str = Form(...),
) -> JSONResponse:
    from src.agents.orchestrator import InterviewOrchestrator

    orchestrator = InterviewOrchestrator(db, redis)
    session_svc = SessionService(db, redis)
    record_repo = RecordRepository(db)

    state = await session_svc.get_session_state(session_id)
    current_q = state.current_question or {}

    # Log candidate answer
    state.conversation_history.append({
        "role": "candidate",
        "content": answer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    db.add(ConversationLog(session_id=session_id, role="candidate", content=answer))

    # Persist record
    record = InterviewRecord(
        session_id=session_id,
        question_id=current_q.get("question_id", str(uuid.uuid4())),
        question_text=current_q.get("text", ""),
        question_skill=current_q.get("skill", "general"),
        question_difficulty=current_q.get("difficulty", "intermediate"),
        candidate_answer=answer,
    )
    record = await record_repo.create(record)
    state.questions_asked += 1

    result = await orchestrator.process_answer(state, answer)
    evaluation = result["evaluation"]
    decision = result["decision"]
    state = result["state"]

    # Save evaluation
    db.add(EvaluationResult(
        record_id=record.id,
        score=evaluation["score"],
        feedback=evaluation["feedback"],
        strengths=evaluation.get("strengths", []),
        weaknesses=evaluation.get("weaknesses", []),
    ))

    action = decision["action"]

    if action == "end_interview":
        state.status = SessionStatus.COMPLETED.value
        state.current_question = None
        await session_svc.update_session_state(state)
        report_data = await orchestrator.evaluate_and_report(session_id)
        return resp.success(data={
            "action": "end_interview",
            "evaluation": evaluation,
            "report": report_data,
        })

    # Next question or follow-up
    question_id = str(uuid.uuid4())
    state.current_question = {
        "question_id": question_id,
        "text": decision["question_text"],
        "topic": decision["topic"],
        "skill": decision["topic"],
        "difficulty": current_q.get("difficulty", "intermediate"),
    }
    state.conversation_history.append({
        "role": "agent",
        "content": decision["question_text"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await session_svc.update_session_state(state)
    db.add(ConversationLog(session_id=session_id, role="agent", content=decision["question_text"]))
    await db.flush()
    await db.commit()

    return resp.success(data={
        "action": action,
        "evaluation": evaluation,
        "next_question": {
            "question_id": question_id,
            "text": decision["question_text"],
            "topic": decision["topic"],
        },
    })


# ── REST: Force-End Interview ──────────────────────────────────────────────

@router.post(
    "/interview/{session_id}/end",
    summary="Force-end an interview",
    description="Immediately ends the interview and triggers report generation.",
)
async def end_interview(
    session_id: uuid.UUID,
    db: DbSession,
    redis: RedisClient,
) -> JSONResponse:
    try:
        from src.agents.orchestrator import InterviewOrchestrator
        orchestrator = InterviewOrchestrator(db, redis)
        await orchestrator.evaluate_and_report(session_id)
    except Exception as exc:
        logger.error("Post-interview evaluation failed on force-end: {}", exc)

    return resp.success(message="Interview ended. Report generation has been triggered.")


# ── WebSocket: OpenAI Realtime Voice Interview ─────────────────────────────

@router.websocket("/interview/{session_id}/realtime")
async def realtime_interview_stream(session_id: uuid.UUID, websocket: WebSocket) -> None:
    """
    Real-time voice interview via OpenAI Realtime API.

    This endpoint relays audio bidirectionally between the browser and OpenAI's
    Realtime API. The model acts as a conversational interviewer — our server
    handles tool calls (evaluate_answer, end_interview) and persists data.
    """
    await websocket.accept()
    logger.info("Realtime WS connected | session={}", session_id)

    async with AsyncSessionFactory() as db:
        redis = get_redis_client()
        session_svc = SessionService(db, redis)

        try:
            # Verify session
            try:
                session = await session_svc.get_session(session_id)
            except NotFoundError:
                await _ws_send_error(websocket, "Session not found")
                await websocket.close(code=4004)
                return

            if session.status != SessionStatus.IN_PROGRESS:
                await _ws_send_error(
                    websocket,
                    f"Session is '{session.status.value}'. Setup the interview first.",
                )
                await websocket.close(code=4003)
                return

            state = await session_svc.get_session_state(session_id)
            config_dict = state.interview_config or {}
            config = InterviewConfig(**config_dict) if config_dict else InterviewConfig()

            # Launch the realtime session
            from src.services.realtime_session import RealtimeInterviewSession

            rt_session = RealtimeInterviewSession(
                session_id=session_id,
                state=state,
                config=config,
                db=db,
                redis=redis,
            )
            await rt_session.run(websocket)

        except WebSocketDisconnect:
            logger.info("Realtime WS client disconnected | session={}", session_id)
        except Exception as exc:
            logger.error("Realtime WS error | session={} | err={}", session_id, exc)
            try:
                await _ws_send_error(websocket, "An internal error occurred.")
                await websocket.close(code=1011)
            except Exception:
                pass


# ── Helpers ────────────────────────────────────────────────────────────────

async def _ws_send_error(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_text(json.dumps({"type": "error", "message": message}))
    except Exception:
        pass
