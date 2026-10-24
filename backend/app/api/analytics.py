"""Admin analytics + a manual trigger for the reminder job (KT 4.5)."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.analytics.analytics_service import compute_analytics
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.models import User
from app.notifications.reminder_service import run_due_date_reminders
from app.schemas.schemas import AnalyticsResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    today = date.today()
    to_d = to_date or today.isoformat()
    from_d = from_date or (today - timedelta(days=365)).isoformat()
    try:
        return compute_analytics(db, from_d, to_d)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dates must be YYYY-MM-DD")


@router.post("/reminders/run")
def run_reminders(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Manually trigger the due-date reminder job (also runs on a schedule)."""
    report = run_due_date_reminders(db)
    return {
        "checked": report.checked,
        "sent": report.sent,
        "skipped_already_sent": report.skipped_already_sent,
        "failed": report.failed,
        "transports": report.transports,
        "details": report.details,
    }
