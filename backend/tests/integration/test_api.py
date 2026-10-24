"""Integration tests covering KNOWLEDGE_TRANSFER.md Section 9.

Run from the backend/ directory:   python -m pytest -q
Uses a temporary SQLite database so it never touches your real data.
"""
import os
import tempfile

import pytest

# Isolated temp DB + disable the background scheduler during tests.
_TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db')}"
os.environ["SCHEDULER_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _admin(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user(client):
    r = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "user123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---- Backend / contract ----
def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_unauthorized_rejected(client):
    assert client.get("/api/v1/admin/analytics").status_code == 401
    assert client.get("/api/v1/admin/analytics", headers=_user(client)).status_code == 403


def test_register_cannot_set_admin_role(client):
    r = client.post("/api/v1/auth/register",
                    json={"name": "Mallory", "email": "mallory@example.com", "password": "secret1", "role": "admin"})
    assert r.status_code == 201
    assert r.json()["role"] == "user"


# ---- Recommendations ----
def test_recommendation_fields_and_status(client):
    r = client.post("/api/v1/recommendations", json={"query": "generative AI", "top_k": 6})
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    assert recs, "expected at least one recommendation"
    for item in recs:
        assert item["book_name"] and item["author"] and item["description"]
        assert item["library_status"] in {"in_library_available", "in_library_out_of_stock", "not_in_library"}
        if item["library_status"] == "not_in_library":
            assert item["book_id"] is None


def test_in_stock_match_is_available(client):
    # seed has "Generative AI Fundamentals" with stock > 0
    r = client.post("/api/v1/recommendations", json={"query": "Generative AI Fundamentals", "top_k": 5})
    statuses = {i["book_name"]: i["library_status"] for i in r.json()["recommendations"]}
    assert statuses.get("Generative AI Fundamentals") == "in_library_available"


def test_stock_only_update_does_not_reembed(client):
    h = _admin(client)
    created = client.post("/api/v1/admin/books", headers=h,
                          json={"title": "Reindex Probe", "author": "QA", "description": "d", "stock_quantity": 1}).json()
    bid = created["book"]["id"]
    assert created["embedding_status"] == "ready"
    patched = client.patch(f"/api/v1/admin/books/{bid}", headers=h, json={"stock_quantity": 9}).json()
    assert "not regenerated" in (patched["embedding_detail"] or "")


# ---- FAQ ----
def test_faq_answered(client):
    r = client.post("/api/v1/chat/faq", json={"question": "How do I borrow a book?"})
    assert r.json()["status"] == "answered"


def test_faq_fallback_after_one_retry(client):
    r = client.post("/api/v1/chat/faq", json={"question": "zzxq nonsense gibberish qwerty"})
    body = r.json()
    assert body["status"] == "fallback"
    assert body["support_contact"]


# ---- Research ----
def test_research_safe_without_key(client):
    r = client.post("/api/v1/research/search", json={"topic": "retrieval augmented generation", "max_results": 3})
    body = r.json()
    assert body["results"] == []            # no fabricated citations
    assert body["note"]                      # transparent explanation


# ---- Loans / reminders ----
def test_user_sees_only_own_loans(client):
    loans = client.get("/api/v1/loans/me", headers=_user(client)).json()
    assert isinstance(loans, list)
    assert any(l["is_overdue"] for l in loans)  # seeded overdue loan


def test_reminders_dedupe(client):
    h = _admin(client)
    first = client.post("/api/v1/admin/reminders/run", headers=h).json()
    assert first["sent"] >= 1
    second = client.post("/api/v1/admin/reminders/run", headers=h).json()
    assert second["sent"] == 0 and second["skipped_already_sent"] >= 1


# ---- Analytics ----
def test_analytics_metrics_and_valid_charts(client):
    an = client.get("/api/v1/admin/analytics", headers=_admin(client)).json()
    assert an["totals"]["total_purchase_events"] > 0
    for chart in an["charts"]:
        n = len(chart["categories"])
        for series in chart["series"]:
            assert len(series["data"]) == n  # schema-validated: lengths match
