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
