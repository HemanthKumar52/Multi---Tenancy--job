"""Native inbox connectors (optional / gated).

The MVP path is the forwarding-alias webhook (no Google verification needed). These connectors
let a user connect their real inbox later:

* **IMAP** (stdlib ``imaplib``) — works today with an app password; good for any provider.
* **Gmail API** — uses the REST API with an OAuth access token (no extra deps). NOTE: the
  ``gmail.readonly`` scope is *restricted*; broad production use requires Google OAuth app
  verification + an annual CASA security assessment (see PLAN.md). Treat as a paid add-on.

Both normalize a message to (from, subject, body) and feed the shared ``ingest_email`` pipeline.
"""
from __future__ import annotations

import base64
import email
from email.header import decode_header, make_header

import httpx

from app.db.base import SessionLocal
from app.services.inbox.ingest import ingest_email


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _plain_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(
                    part.get("Content-Disposition", "")):
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", "replace")
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", "replace")


def poll_imap(*, host: str, user: str, password: str, tenant_id: str,
              mailbox: str = "INBOX", limit: int = 25, session_factory=SessionLocal) -> int:
    """Fetch unseen messages over IMAP and ingest them. Returns the count ingested."""
    import imaplib

    conn = imaplib.IMAP4_SSL(host)
    ingested = 0
    try:
        conn.login(user, password)
        conn.select(mailbox)
        _typ, data = conn.search(None, "UNSEEN")
        ids = (data[0].split() if data and data[0] else [])[:limit]
        db = session_factory()
        try:
            for mid in ids:
                _typ, msg_data = conn.fetch(mid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                ingest_email(db, tenant_id,
                             from_addr=_decode(msg.get("From")),
                             subject=_decode(msg.get("Subject")),
                             body=_plain_body(msg), commit=True)
                ingested += 1
        finally:
            db.close()
    finally:
        conn.logout()
    return ingested


def poll_gmail(*, access_token: str, tenant_id: str, query: str = "newer_than:7d",
               limit: int = 25, session_factory=SessionLocal, timeout: float = 20.0) -> int:
    """Fetch messages via the Gmail REST API using an OAuth access token. Returns count ingested."""
    base = "https://gmail.googleapis.com/gmail/v1/users/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    listing = httpx.get(f"{base}/messages", headers=headers,
                        params={"q": query, "maxResults": limit}, timeout=timeout)
    listing.raise_for_status()
    messages = listing.json().get("messages", [])

    db = session_factory()
    ingested = 0
    try:
        for m in messages:
            full = httpx.get(f"{base}/messages/{m['id']}", headers=headers,
                             params={"format": "full"}, timeout=timeout).json()
            payload = full.get("payload", {})
            hdrs = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            ingest_email(db, tenant_id,
                         from_addr=hdrs.get("from", ""), subject=hdrs.get("subject", ""),
                         body=_extract_gmail_body(payload), commit=True)
            ingested += 1
    finally:
        db.close()
    return ingested


def _extract_gmail_body(payload: dict) -> str:
    def _decode_part(part) -> str:
        data = (part.get("body") or {}).get("data")
        if not data:
            return ""
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")

    if payload.get("mimeType") == "text/plain":
        return _decode_part(payload)
    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain":
            return _decode_part(part)
        nested = _extract_gmail_body(part)
        if nested:
            return nested
    return ""
