"""DirectorAgent — config-aware interview director using LangChain.

V2 director: reads InterviewConfig, enforces follow-up limits per topic,
injects depth/style/focus into prompt, tracks topics_covered, escalates
difficulty based on scores.
"""
from __future__ import annotations

from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agents.base import BaseAgent
from src.config.settings import settings
from src.schemas.interview_config import InterviewConfig
from src.utils.logger import logger


class DirectorDecision(BaseModel):
    """Structured output for director decisions."""
    action: str = Field(description="follow_up | next_question | end_interview")
    question_text: str = Field(default="", description="The follow-up or new question text")
    topic: str = Field(default="general", description="Skill/topic being tested")
    reasoning: str = Field(default="", description="One sentence internal reasoning")


SYSTEM_TEMPLATE = """You are an expert interview director conducting a professional, domain-agnostic interview.

Your job is to decide the next action after a candidate answers:
1. "follow_up" — the answer was incomplete, vague, or needs clarification; ask a targeted follow-up
2. "next_question" — the answer was satisfactory; move to a new topic or skill area
3. "end_interview" — all major topics have been covered OR the question count limit is reached

Rules:
- Be adaptive: adjust question depth based on the answer quality
- Never repeat a question already asked
- Stay within the domain and seniority level of the role
- If max_questions is reached, always return "end_interview"
{config_rules}"""

HUMAN_TEMPLATE = """CONVERSATION SO FAR:
{history_text}

CANDIDATE'S LATEST ANSWER:
{latest_transcript}

PROGRESS: {questions_asked} question(s) asked. Max allowed: {max_questions}.{end_note}
{context_block}

TOPICS COVERED SO FAR: {topics_covered}
FOLLOW-UPS ON CURRENT TOPIC: {follow_ups_this_topic}

Decide the next action."""


class DirectorAgent(BaseAgent):
    name = "director"

    def _build_config_rules(self, config: InterviewConfig) -> str:
        rules = []
        if config.max_follow_ups_per_topic > 0:
            rules.append(
                f"- Maximum {config.max_follow_ups_per_topic} follow-up questions per topic. "
                f"After that, move to the next topic."
            )
        if config.depth == "deep":
            rules.append(
                "- DEPTH=deep: Escalate difficulty when the candidate scores well. "
                "Ask probing edge-case questions."
            )
        elif config.depth == "surface":
            rules.append(
                "- DEPTH=surface: Keep questions at a high level. "
                "Do not probe deeply into implementation details."
            )
        if config.style == "technical":
            rules.append("- STYLE=technical: Focus on coding, system design, and technical depth.")
        elif config.style == "behavioral":
            rules.append("- STYLE=behavioral: Focus on STAR-method behavioral questions.")
        if config.focus_areas:
            rules.append(f"- FOCUS AREAS: Prioritise these topics: {', '.join(config.focus_areas)}")
        return "\n".join(rules)

    def build_chain(self) -> Runnable:
        # Chain is built dynamically in run() because config varies per call
        raise NotImplementedError("Use run() directly — config varies per invocation.")

    async def run(self, ctx: dict) -> dict:
        """
        ctx keys:
          - state: SessionState dict or object
          - latest_transcript: str
          - max_questions: int
          - config: dict (InterviewConfig fields)
          - avg_score: float (optional, for difficulty escalation)
        """
        state = ctx["state"]
        latest_transcript = ctx.get("latest_transcript", "")
        config_dict = ctx.get("config") or {}
        config = InterviewConfig(**config_dict) if config_dict else InterviewConfig()
        max_questions = ctx.get("max_questions", config.max_questions)

        # Read state fields
        if hasattr(state, "model_dump"):
            s = state
            questions_asked = s.questions_asked
            conversation_history = s.conversation_history
            jd_context = s.jd_context
            topics_covered = s.topics_covered
            follow_ups_this_topic = s.follow_ups_this_topic
            current_topic = s.current_topic
        else:
            questions_asked = state.get("questions_asked", 0)
            conversation_history = state.get("conversation_history", [])
            jd_context = state.get("jd_context")
            topics_covered = state.get("topics_covered", [])
            follow_ups_this_topic = state.get("follow_ups_this_topic", 0)
            current_topic = state.get("current_topic", "")

        # Enforce follow-up limit locally
        force_next_topic = follow_ups_this_topic >= config.max_follow_ups_per_topic
        force_end = questions_asked >= max_questions

        config_rules = self._build_config_rules(config)
        if force_next_topic:
            config_rules += (
                f"\n- IMPORTANT: You have already asked {follow_ups_this_topic} follow-ups on "
                f"'{current_topic}'. You MUST move to a new topic (action=next_question)."
            )

        # Build context block
        context_block = ""
        if jd_context:
            jd = jd_context if isinstance(jd_context, dict) else jd_context
            context_block = (
                f"\nINTERVIEW CONTEXT:\n"
                f"- Role: {jd.get('job_title', 'Professional')}\n"
                f"- Domain: {jd.get('domain', '')}\n"
                f"- Seniority: {jd.get('seniority_level', '')}\n"
                f"- Required skills: {', '.join(jd.get('required_skills', []))}\n"
                f"- Candidate skills: {', '.join(jd.get('candidate_skills', []))}\n"
                f"- Skill gaps to probe: {', '.join(jd.get('skill_gaps', []))}\n"
                f"- Candidate experience: {jd.get('candidate_experience_years', 'unknown')} years"
            )

        recent = conversation_history[-10:]
        history_text = (
            "\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent)
            if recent else "No previous conversation yet."
        )

        end_note = ""
        if force_end:
            end_note = "\nNOTE: The question limit has been reached. You MUST return action='end_interview'."

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_TEMPLATE),
            ("human", HUMAN_TEMPLATE),
        ])
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            max_tokens=512,
        ).with_structured_output(DirectorDecision)

        chain = prompt | llm

        logger.debug("DirectorAgent | q_asked={} force_end={} follow_ups={}",
                      questions_asked, force_end, follow_ups_this_topic)

        decision: DirectorDecision = await chain.ainvoke({
            "config_rules": config_rules,
            "history_text": history_text,
            "latest_transcript": latest_transcript,
            "questions_asked": questions_asked,
            "max_questions": max_questions,
            "end_note": end_note,
            "context_block": context_block,
            "topics_covered": ", ".join(topics_covered) if topics_covered else "none",
            "follow_ups_this_topic": follow_ups_this_topic,
        })

        action = decision.action
        # Enforce constraints
        if force_end:
            action = "end_interview"
        if force_next_topic and action == "follow_up":
            action = "next_question"

        result = {
            "action": action,
            "question_text": decision.question_text if action != "end_interview" else "",
            "topic": decision.topic,
            "reasoning": decision.reasoning,
        }
        logger.info("DirectorAgent decision | action={} topic={}", result["action"], result["topic"])
        return result

    async def generate_opening(self, ctx: dict) -> dict:
        """Generate the very first question for the interview."""
        state = ctx["state"]
        config_dict = ctx.get("config") or {}
        config = InterviewConfig(**config_dict) if config_dict else InterviewConfig()

        jd_context = state.jd_context if hasattr(state, "jd_context") else state.get("jd_context")
        context_block = ""
        if jd_context:
            jd = jd_context
            context_block = (
                f"\nINTERVIEW CONTEXT:\n"
                f"- Role: {jd.get('job_title', 'Professional')}\n"
                f"- Domain: {jd.get('domain', '')}\n"
                f"- Seniority: {jd.get('seniority_level', '')}\n"
                f"- Required skills: {', '.join(jd.get('required_skills', []))}\n"
                f"- Candidate skills: {', '.join(jd.get('candidate_skills', []))}\n"
                f"- Skill gaps to probe: {', '.join(jd.get('skill_gaps', []))}"
            )

        config_rules = self._build_config_rules(config)

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_TEMPLATE),
            ("human", """Generate the FIRST interview question for this candidate.
{context_block}

Start with a warm opening question that assesses the candidate's background
relevant to the role."""),
        ])
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,
            max_tokens=256,
        ).with_structured_output(DirectorDecision)

        chain = prompt | llm
        decision: DirectorDecision = await chain.ainvoke({
            "config_rules": config_rules,
            "context_block": context_block,
        })

        return {
            "action": "next_question",
            "question_text": decision.question_text or "Tell me about yourself and your relevant experience.",
            "topic": decision.topic or "background",
            "reasoning": "opening question",
        }
