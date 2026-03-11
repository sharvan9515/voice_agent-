"""Shared async OpenAI client singleton used by all LLM services."""
from __future__ import annotations

import json
import re
from typing import Optional

from openai import AsyncOpenAI

from src.config.settings import settings

_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def chat_json(system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> dict:
    """
    Call OpenAI chat completions and return parsed JSON dict.
    Uses response_format=json_object for reliable JSON output.
    Raises ValueError if JSON cannot be parsed.
    """
    client = get_openai_client()
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_tokens=max_tokens or settings.OPENAI_MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"OpenAI returned non-JSON content: {content[:200]}")
