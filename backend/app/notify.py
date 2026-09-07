"""Best-effort email notifications — gap reports (corpus doesn't cover a
real question) and contact-form submissions. Ported from the legacy
backend/app.py's gap-notification logic and extended to cover contact.

Uses a Gmail App Password (myaccount.google.com/apppasswords), never the
account password. Unset any of SMTP_USER/SMTP_APP_PASSWORD/*_NOTIFY_EMAIL
and the relevant function just logs to stdout instead of emailing — a
broken mail config must degrade, never surface as a 500 to a visitor.
"""

from __future__ import annotations

import smtplib
import time
from collections import deque
from email.message import EmailMessage

from .config import Settings

GAP_DEDUPE_WINDOW = 600  # seconds


class GapDeduper:
    def __init__(self):
        self._recent: deque[tuple[str, float]] = deque()

    def is_duplicate(self, question: str, now: float | None = None) -> bool:
        now = now if now is not None else time.monotonic()
        key = question.strip().lower()
        while self._recent and now - self._recent[0][1] > GAP_DEDUPE_WINDOW:
            self._recent.popleft()
        if any(q == key for q, _ in self._recent):
            return True
        self._recent.append((key, now))
        return False


def send_gap_email(settings: Settings, question: str, topics: list[str]) -> None:
    if not (settings.gap_notify_email and settings.smtp_user and settings.smtp_app_password):
        print(f"[gap] (email not configured) question={question!r} topics={topics}")
        return
    msg = EmailMessage()
    msg["Subject"] = "Chappie couldn't answer a recruiter question"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.gap_notify_email
    topic_line = ", ".join(topics) if topics else "(no specific topic detected)"
    msg.set_content(
        "A visitor asked Chappie something the corpus doesn't cover:\n\n"
        f'  "{question}"\n\n'
        f"Detected topic(s): {topic_line}\n\n"
        "If this is a real gap, add it to content/ and rebuild the corpus."
    )
    _send(settings, msg)


def send_report_email(
    settings: Settings,
    question: str,
    answer_text: str,
    reason: str,
    trace_id: str | None,
    contact_email: str,
) -> None:
    if not (settings.report_notify_email and settings.smtp_user and settings.smtp_app_password):
        print(f"[report] (email not configured) question={question!r} reason={reason!r} trace_id={trace_id!r}")
        return
    msg = EmailMessage()
    msg["Subject"] = "Chappie: a visitor flagged an answer as wrong or unhelpful"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.report_notify_email
    if contact_email:
        msg["Reply-To"] = contact_email
    lines = [
        "A visitor flagged one of Chappie's answers:\n",
        f'  Question: "{question}"\n',
        f"  Answer given: {answer_text or '(no answer text captured)'}\n",
        f"  What they said was wrong: {reason or '(no reason given)'}\n",
    ]
    if trace_id:
        lines.append(f"  Trace id: {trace_id} — look it up on the Observability page for the full retrieval/generation timeline.\n")
    if contact_email:
        lines.append(f"  They left a reply-to address: {contact_email}\n")
    msg.set_content("".join(lines))
    _send(settings, msg)


def send_contact_email(settings: Settings, name: str, email: str, message: str) -> None:
    if not (settings.contact_notify_email and settings.smtp_user and settings.smtp_app_password):
        print(f"[contact] (email not configured) name={name!r} email={email!r} message={message!r}")
        return
    msg = EmailMessage()
    msg["Subject"] = f"Portfolio contact form: {name}"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.contact_notify_email
    msg["Reply-To"] = email
    msg.set_content(f"From: {name} <{email}>\n\n{message}")
    _send(settings, msg)


def _send(settings: Settings, msg: EmailMessage) -> None:
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(settings.smtp_user, settings.smtp_app_password)
            smtp.send_message(msg)
    except Exception as e:  # noqa: BLE001 — mail failure must never surface to the visitor
        print(f"[notify] email failed: {e}")
