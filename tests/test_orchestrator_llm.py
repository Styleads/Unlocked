"""Discovery must give member2 its LLM, or Agent 1's text-only rules are never structured."""
from api import orchestrator


def test_no_key_means_deterministic_normalizer(monkeypatch):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert orchestrator._normalizer_llm() is None


def test_key_gives_member2_client(monkeypatch):
    sentinel = object()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    monkeypatch.setattr(orchestrator, "default_client", lambda: sentinel)
    assert orchestrator._normalizer_llm() is sentinel


def test_broken_client_does_not_fail_discovery(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")

    def boom():
        raise ImportError("sdk missing")

    monkeypatch.setattr(orchestrator, "default_client", boom)
    assert orchestrator._normalizer_llm() is None


def test_email_action_without_key_uses_template_without_errors(monkeypatch, tmp_path, caplog):
    import logging
    from fastapi.testclient import TestClient
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    db = str(tmp_path / "t.db")
    monkeypatch.setenv("DB_PATH", db)
    monkeypatch.setattr("api.database.DEFAULT_DB_PATH", db)
    from api.main import app
    with TestClient(app) as c, caplog.at_level(logging.WARNING):
        sid = c.post("/api/sessions", json={"context": {"state": "Karnataka", "occupation": "student",
                                                        "interests": ["scholarship"]}}).json()["session_id"]
        scheme = c.post(f"/api/sessions/{sid}/discover", json={"search_scope": "fallback",
                                                               "enable_fallback": True}).json()["schemes"][0]["id"]
        r = c.post(f"/api/sessions/{sid}/actions/email", json={"scheme_id": scheme, "purpose": "clarification",
                                                               "question": "Which documents are needed?"})
    assert r.status_code == 200 and r.json()["generated_by"] == "template"
    assert not any("email_draft failed" in m for m in caplog.messages)
