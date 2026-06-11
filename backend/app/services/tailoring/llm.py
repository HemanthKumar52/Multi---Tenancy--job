"""Thin Claude wrapper that degrades gracefully when no API key is configured."""
from __future__ import annotations

import json

from app.config import settings


def llm_available() -> bool:
    return settings.llm_enabled


def complete(system: str, user: str, *, model: str | None = None, max_tokens: int = 2000) -> str:
    """Single-shot completion. Raises if no key is configured (callers guard with ``llm_available``)."""
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=model or settings.anthropic_tailor_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


def complete_json(system: str, user: str, *, model: str | None = None, max_tokens: int = 2000):
    """Completion expected to return JSON; tolerant of code fences."""
    raw = complete(system, user, model=model, max_tokens=max_tokens).strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    return json.loads(raw)
