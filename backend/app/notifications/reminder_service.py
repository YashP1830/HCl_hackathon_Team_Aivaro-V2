"""Due-date reminder service (KT 4.5 / C-5).

Finds overdue, unreturned loans and emails the borrower. Duplicate sends are
prevented by stamping ``reminder_sent_at`` on the loan. Returned loans never get
reminders. Reads loan records only (not purchases).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.notifications.email_adapter import send_email
from app.repositories import repositories as repo

logger = logging.getLogger("app.notifications.reminder")


@dataclass
class ReminderReport:
    checked: int = 0
    sent: int = 0
    skipped_already_sent: int = 0
    failed: int = 0
    transports: dict[str, int] = field(default_factory=dict)
    details: list[str] = field(default_factory=list)


def _should_send(loan, now: datetime) -> bool:
    if loan.reminder_sent_at is None:
        return True
    if settings.reminder_cadence == "daily":
        # send at most once per calendar day
        last = loan.reminder_sent_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return last.date() < now.date()
    return False  # "once" policy: already sent


def run_due_date_reminders(db: Session) -> ReminderReport:
    report = ReminderReport()
    now = datetime.now(timezone.utc)
    loans = repo.overdue_unreturned_loans(db)
    report.checked = len(loans)

    for loan in loans:
        if not _should_send(loan, now):
            report.skipped_already_sent += 1
            continue

        user = repo.get_user(db, loan.user_id)
        book = repo.get_book(db, loan.book_id)
        if user is None or book is None:
            report.failed += 1
            continue

        due = loan.due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        days_overdue = (now - due).days

        subject = f"Reminder: '{book.title}' is overdue"
        body = (
            f"Hi {user.name},\n\n"
            f"Our records show the book '{book.title}' by {book.author} was due on "
            f"{due.date().isoformat()} and has not yet been returned "
            f"({days_overdue} day(s) overdue).\n\n"
            f"Please return it at your earliest convenience.\n\n"
            f"If you have already returned it, please ignore this message or contact "
            f"{settings.support_email}.\n\n"
            f"Thank you,\nThe Library Team"
        )

        result = send_email(to=user.email, subject=subject, body=body)
        if result.ok:
            loan.reminder_sent_at = now
            db.add(loan)
            db.commit()
            report.sent += 1
            report.transports[result.transport] = report.transports.get(result.transport, 0) + 1
            report.details.append(f"sent to {user.email} for loan {loan.id} via {result.transport}")
        else:
            report.failed += 1
            report.details.append(f"FAILED for loan {loan.id}: {result.detail}")

    logger.info(
        "Reminder run: checked=%s sent=%s skipped=%s failed=%s",
        report.checked, report.sent, report.skipped_already_sent, report.failed,
    )
    return report
