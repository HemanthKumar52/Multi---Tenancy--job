"""Notifications. Telegram when configured; otherwise records to the log/DB for the dashboard."""
from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger("notify")


def notify(user_chat_id: str | None, title: str, body: str) -> dict:
    """Best-effort notification. Always returns a result; never raises into the caller."""
    payload = {"title": title, "body": body, "delivered": False, "channel": "none"}

    if settings.telegram_bot_token and user_chat_id:
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": user_chat_id, "text": f"*{title}*\n\n{body}", "parse_mode": "Markdown"},
                timeout=10,
            )
            resp.raise_for_status()
            payload.update(delivered=True, channel="telegram")
            return payload
        except Exception as exc:  # noqa: BLE001
            log.warning("Telegram notify failed: %s", exc)

    # Fallback: log it (the dashboard reads persisted notifications from the DB).
    log.info("NOTIFY[%s] %s — %s", "in-app", title, body)
    payload.update(channel="in-app")
    return payload
