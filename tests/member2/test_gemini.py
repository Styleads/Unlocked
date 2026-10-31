import pytest

from member2.llm import GeminiClient, LLMError, default_client


def _client(monkeypatch, response):
    client = GeminiClient(api_key="test-key")
    monkeypatch.setattr(client, "_post", lambda body: response)
    return client


def _ok(text):
    return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}


def test_returns_text(monkeypatch):
    assert _client(monkeypatch, _ok(' {"a": 1} ')).complete_json("s", "u") == '{"a": 1}'


@pytest.mark.parametrize("response", [
    {},
    {"candidates": []},
    {"promptFeedback": {"blockReason": "SAFETY"}},
    {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{"}]}}]},
    {"candidates": [{"finishReason": "SAFETY"}]},
    {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "  "}]}}]},
])
def test_unusable_responses_raise_llm_error(monkeypatch, response):
    with pytest.raises(LLMError):
        _client(monkeypatch, response).complete_json("s", "u")


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(LLMError):
        GeminiClient()


def test_default_client_prefers_gemini_when_key_set(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert isinstance(default_client(), GeminiClient)


def test_transient_errors_are_retried(monkeypatch):
    from member2 import llm

    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    client = GeminiClient(api_key="test-key")
    calls = []

    def flaky(body):
        calls.append(1)
        if len(calls) < 3:
            raise llm._Transient(503)
        return _ok("{}")

    monkeypatch.setattr(client, "_post_once", flaky)
    assert client.complete_json("s", "u") == "{}"
    assert len(calls) == 3


def test_persistent_overload_raises_llm_error(monkeypatch):
    from member2 import llm

    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    client = GeminiClient(api_key="test-key")

    def always(body):
        raise llm._Transient(503)

    monkeypatch.setattr(client, "_post_once", always)
    with pytest.raises(LLMError):
        client.complete_json("s", "u")
