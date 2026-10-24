"""Daily reminder scheduler (KT C / jobs).

Uses a stdlib background thread (no extra dependency, so nothing to break on a
fresh Windows install). The job is idempotent -- it relies on the reminder
service's dedupe -- so running it hourly is safe under the "once" policy.

It can also be run as a one-shot from the CLI:
    python -m app.jobs.scheduler --once
"""
from __future__ import annotations

import argparse
import logging
import threading
import time

from app.core.config import settings
from app.db.session import SessionLocal
from app.notifications.reminder_service import run_due_date_reminders

logger = logging.getLogger("app.jobs.scheduler")

_thread: threading.Thread | None = None
_stop = threading.Event()


def run_once() -> None:
    db = SessionLocal()
    try:
        report = run_due_date_reminders(db)
        logger.info("Scheduled reminder run complete: %s", report)
    except Exception:
        logger.exception("Scheduled reminder run failed")
    finally:
        db.close()


def _loop() -> None:
    # small initial delay so startup isn't blocked
    if _stop.wait(5):
        return
    while not _stop.is_set():
        run_once()
        if _stop.wait(settings.scheduler_interval_seconds):
            break


def start_scheduler() -> None:
    global _thread
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled via settings")
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="reminder-scheduler", daemon=True)
    _thread.start()
    logger.info("Reminder scheduler started (interval=%ss)", settings.scheduler_interval_seconds)


def stop_scheduler() -> None:
    _stop.set()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Library reminder job")
    parser.add_argument("--once", action="store_true", help="Run a single reminder pass and exit")
    args = parser.parse_args()
    if args.once:
        run_once()
    else:
        start_scheduler()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_scheduler()
