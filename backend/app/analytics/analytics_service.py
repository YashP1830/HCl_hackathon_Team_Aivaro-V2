"""Admin analytics (KT 4.5 / C-6).

- Reads only confirmed purchase events in a time window.
- Computes ALL metrics deterministically in Python (never via the LLM).
- Asks the LLM for a narrative explanation of the precomputed metrics.
- Builds + schema-validates chart data before returning it.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, time, timezone

from sqlalchemy.orm import Session

from app.ai.llm import get_llm
from app.repositories import repositories as repo
from app.schemas.schemas import AnalyticsResponse, ChartData, ChartSeries

logger = logging.getLogger("app.analytics")


def _parse_date(value: str, *, end: bool = False) -> datetime:
    d = datetime.strptime(value, "%Y-%m-%d").date()
    t = time.max if end else time.min
    return datetime.combine(d, t, tzinfo=timezone.utc)


def compute_analytics(db: Session, from_date: str, to_date: str) -> AnalyticsResponse:
    start = _parse_date(from_date)
    end = _parse_date(to_date, end=True)
    events = repo.purchases_between(db, start, end)

    # ---- Deterministic metrics (Python) ----
    total_purchases = len(events)
    total_units = sum(e.quantity for e in events)
    total_revenue = round(sum(e.amount for e in events), 2)
    unique_titles = len({e.book_title for e in events if e.book_title})

    by_title_units: dict[str, int] = defaultdict(int)
    by_title_revenue: dict[str, float] = defaultdict(float)
    by_genre_units: dict[str, int] = defaultdict(int)
    by_month_revenue: dict[str, float] = defaultdict(float)

    for e in events:
        title = e.book_title or "(unknown)"
        by_title_units[title] += e.quantity
        by_title_revenue[title] += e.amount
        by_genre_units[e.genre or "(uncategorized)"] += e.quantity
        month = e.purchased_at.strftime("%Y-%m")
        by_month_revenue[month] += e.amount

    top_books = sorted(
        (
            {"title": t, "units": by_title_units[t], "revenue": round(by_title_revenue[t], 2)}
            for t in by_title_units
        ),
        key=lambda x: (x["units"], x["revenue"]),
        reverse=True,
    )[:10]

    totals = {
        "total_purchase_events": float(total_purchases),
        "total_units": float(total_units),
        "total_revenue": float(total_revenue),
        "unique_titles": float(unique_titles),
    }

    # ---- Charts (built in code, then validated) ----
    charts: list[ChartData] = []

    top5 = top_books[:5]
    if top5:
        charts.append(
            ChartData(
                type="bar",
                title="Top books by units sold",
                categories=[b["title"] for b in top5],
                series=[ChartSeries(label="Units", data=[float(b["units"]) for b in top5])],
            )
        )

    if by_month_revenue:
        months = sorted(by_month_revenue)
        charts.append(
            ChartData(
                type="line",
                title="Revenue by month",
                categories=months,
                series=[ChartSeries(label="Revenue", data=[round(by_month_revenue[m], 2) for m in months])],
            )
        )

    if by_genre_units:
        genres = sorted(by_genre_units, key=lambda g: by_genre_units[g], reverse=True)[:6]
        charts.append(
            ChartData(
                type="pie",
                title="Units by genre",
                categories=genres,
                series=[ChartSeries(label="Units", data=[float(by_genre_units[g]) for g in genres])],
            )
        )

    charts = _validate_charts(charts)

    # ---- LLM narrative over the precomputed metrics ----
    narrative, llm_used = _narrative(totals, top_books, from_date, to_date)

    return AnalyticsResponse(
        from_date=from_date,
        to_date=to_date,
        totals=totals,
        top_books=top_books,
        narrative=narrative,
        charts=charts,
        llm_used=llm_used,
    )


def _validate_charts(charts: list[ChartData]) -> list[ChartData]:
    """Ensure every series length matches the category count. Drop invalid ones
    rather than returning malformed chart data to the UI."""
    valid: list[ChartData] = []
    for c in charts:
        n = len(c.categories)
        if n == 0:
            continue
        if all(len(s.data) == n for s in c.series) and c.series:
            valid.append(c)
        else:
            logger.warning("Dropping invalid chart '%s' (series/category mismatch)", c.title)
    return valid


def _narrative(totals: dict, top_books: list[dict], from_date: str, to_date: str) -> tuple[str, bool]:
    llm = get_llm()
    facts = (
        f"Window: {from_date} to {to_date}. "
        f"Total purchase events: {int(totals['total_purchase_events'])}. "
        f"Total units: {int(totals['total_units'])}. "
        f"Total revenue: {totals['total_revenue']}. "
        f"Unique titles: {int(totals['unique_titles'])}. "
        f"Top books: {top_books[:5]}."
    )
    system = (
        "You are a data analyst writing a short narrative for a library admin "
        "dashboard. Explain the trends in the PROVIDED metrics only. Do NOT invent "
        "numbers or metrics that are not given. Respond with JSON of the form "
        '{"narrative": "..."}. Keep it to 3-5 sentences.'
    )
    try:
        data = llm.complete_json(system, facts)
        narrative = (data.get("narrative") if isinstance(data, dict) else None) or ""
        narrative = narrative.strip()
        if narrative:
            return narrative, llm.provider == "gemini"
    except Exception:
        logger.exception("LLM narrative failed")

    # deterministic fallback narrative
    if int(totals["total_purchase_events"]) == 0:
        text = f"No purchase events were recorded between {from_date} and {to_date}."
    else:
        leader = top_books[0]["title"] if top_books else "n/a"
        text = (
            f"Between {from_date} and {to_date} the library recorded "
            f"{int(totals['total_purchase_events'])} purchase events covering "
            f"{int(totals['total_units'])} units and {totals['total_revenue']} in revenue "
            f"across {int(totals['unique_titles'])} unique titles. "
            f"The best-selling title was '{leader}'. "
            f"(Narrative generated locally; all metrics are computed exactly in code.)"
        )
    return text, False
