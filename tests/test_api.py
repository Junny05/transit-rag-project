import pytest
from fastapi.testclient import TestClient

from app.gtfs_feed import FeedFetchError


@pytest.fixture
def client(monkeypatch):
    # Import after conftest's session fixture has patched SentenceTransformer.
    from app import main as main_module

    # Avoid real network calls to the MTA feed during startup.
    monkeypatch.setattr(
        main_module,
        "get_current_alerts",
        lambda: ["L train delayed due to signal problems"],
    )
    with TestClient(main_module.app) as c:
        yield c, main_module


def test_health_reports_ready_after_startup(client):
    c, _ = client
    resp = c.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["feed_ok"] is True


def test_ask_returns_answer_when_llm_succeeds(client, monkeypatch):
    c, main_module = client
    monkeypatch.setattr(main_module, "generate_answer", lambda q, ctx: "Yes, the L train is delayed.")

    resp = c.get("/ask", params={"question": "Is the L train delayed?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Yes, the L train is delayed."
    assert body["stale"] is False


def test_ask_returns_502_when_llm_fails(client, monkeypatch):
    c, main_module = client

    def failing_generate(q, ctx):
        raise RuntimeError("Gemini API unavailable")

    monkeypatch.setattr(main_module, "generate_answer", failing_generate)

    resp = c.get("/ask", params={"question": "Is the L train delayed?"})
    assert resp.status_code == 502


def test_ask_rejects_empty_question(client):
    c, _ = client
    resp = c.get("/ask", params={"question": ""})
    assert resp.status_code == 422  # Pydantic/FastAPI validation, not a 500


def test_ask_marks_stale_when_feed_refresh_failed(client, monkeypatch):
    c, main_module = client
    monkeypatch.setattr(main_module, "generate_answer", lambda q, ctx: "some answer")

    # Simulate the feed going down after startup succeeded once.
    main_module._feed_status["ok"] = False
    resp = c.get("/ask", params={"question": "Is the L train delayed?"})
    assert resp.json()["stale"] is True
