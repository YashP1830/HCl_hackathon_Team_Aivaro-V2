"""Email provider adapter.

Primary: SMTP (used when SMTP_HOST + SMTP_USERNAME are configured).
Fallback: write the message to backend/data/outbox as a .eml-style file and log
it, so reminders are fully testable on a fresh machine without a mail server.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from app.core.config import DATA_DIR, settings

logger = logging.getLogger("app.notifications.email")

OUTBOX_DIR = DATA_DIR / "outbox"
OUTBOX_DIR.mkdir(parents=True, exist_ok=True)


class EmailResult:
    def __init__(self, ok: bool, transport: str, detail: str = "") -> None:
        self.ok = ok
        self.transport = transport
        self.detail = detail


def send_email(*, to: str, subject: str, body: str) -> EmailResult:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if settings.smtp_enabled:
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                if settings.smtp_username:
                    server.login(settings.smtp_username, settings.smtp_password)
                server.send_message(msg)
            logger.info("Sent email to %s via SMTP", to)
            return EmailResult(True, "smtp")
        except Exception as exc:
            logger.warning("SMTP send failed, falling back to outbox file: %s", exc)

    # Fallback: persist to outbox
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    safe_to = to.replace("@", "_at_").replace("/", "_")
    path: Path = OUTBOX_DIR / f"{ts}_{safe_to}.eml"
    try:
        path.write_text(str(msg), encoding="utf-8")
        logger.info("Wrote email to outbox: %s", path)
        return EmailResult(True, "outbox", str(path))
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to write outbox email")
        return EmailResult(False, "none", str(exc))
