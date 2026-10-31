"""The single LLM adapter. Everything else in member2 depends only on `LLMClient`,
so tests use a fake and the provider can be swapped without touching callers."""
from __future__ import annotations

import os
import time
from typing import Optional, Protocol

DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"  # alias; pinned names get retired (404)

# Models that accept the server-side `fallbacks: "default"` refusal rescue.
_FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1"}


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> str: ...


class LLMError(RuntimeError):
    """The model returned no usable text (refusal, truncation, empty)."""


class AnthropicClient:
    """Claude via the official SDK. `anthropic` is imported lazily so member2
    imports and runs without it."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        max_tokens: int = 8000,
        effort: str = "low",
        timeout: float = 60.0,
    ) -> None:
        import anthropic

        self.model = model or os.environ.get("UNLOCKED_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens
        self.effort = effort
        # With no key the SDK falls back to ANTHROPIC_API_KEY or an `ant auth login` profile.
        kwargs = {"timeout": timeout}
        if api_key:
            kwargs["api_key"] = api_key
        self._client = anthropic.Anthropic(**kwargs)

    def complete_json(self, system: str, user: str) -> str:
        # No temperature: current models reject non-default sampling parameters.
        params = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": self.effort},
        )
        if self.model in _FALLBACK_MODELS:
            params.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        response = self._client.beta.messages.create(**params)

        if response.stop_reason == "refusal":
            raise LLMError("model declined the request")
        if response.stop_reason == "max_tokens":
            raise LLMError("model output was truncated")
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        if not text:
            raise LLMError("model returned no text")
        return text


_RETRIES = 4


def _daily_quota(exc: Exception) -> bool:
    """True if a 429 body names a per-day quota (its quota id says so)."""
    try:
        body = exc.read().decode("utf-8", "replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - unreadable body: treat as transient
        return False
    return "perday" in body.lower().replace(" ", "")


class _Transient(Exception):
    def __init__(self, code: int) -> None:
        self.code = code


class GeminiClient:
    """Gemini via its REST API, using only the standard library so the free-tier
    option needs no extra install. Key comes from GEMINI_API_KEY or GOOGLE_API_KEY."""

    _URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        max_tokens: int = 8000,
        timeout: float = 60.0,
    ) -> None:
        self.model = model or os.environ.get("UNLOCKED_MODEL", DEFAULT_GEMINI_MODEL)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise LLMError("no Gemini API key set (GEMINI_API_KEY)")
        self.max_tokens = max_tokens
        self.timeout = timeout
        # The concrete model the alias resolved to on the last call (Gemini's "modelVersion").
        self.resolved_model: Optional[str] = None

    def _post(self, body: dict) -> dict:
        # The free tier is often briefly overloaded (503) or rate limited (429).
        for attempt in range(_RETRIES):
            try:
                return self._post_once(body)
            except _Transient as exc:
                if attempt == _RETRIES - 1:
                    raise LLMError(f"Gemini request failed (HTTP {exc.code}) after {_RETRIES} tries") from None
                time.sleep(2 ** (attempt + 1))
        raise LLMError("Gemini request failed")  # unreachable

    def _post_once(self, body: dict) -> dict:
        import json
        import urllib.error
        import urllib.request

        request = urllib.request.Request(
            self._URL.format(model=self.model),
            data=json.dumps(body).encode("utf-8"),
            # Key in a header, not the URL, so it never lands in an error message or log.
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and _daily_quota(exc):
                # A per-day quota won't clear by retrying; fail now.
                raise LLMError("Gemini daily quota exhausted (HTTP 429)") from None
            if exc.code in (429, 500, 502, 503, 504):
                raise _Transient(exc.code) from None
            raise LLMError(f"Gemini request failed (HTTP {exc.code})") from None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise LLMError(f"Gemini request failed ({type(exc).__name__})") from None

    def list_models(self) -> list[str]:
        """Model ids this key can call, to recover from a stale default name."""
        import json
        import urllib.request

        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
            headers={"x-goog-api-key": self.api_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                models = json.loads(response.read().decode("utf-8")).get("models", [])
        except Exception as exc:  # diagnostics only; never include the request
            raise LLMError(f"could not list models ({type(exc).__name__})") from None
        return [
            m["name"].removeprefix("models/")
            for m in models
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]

    def complete_json(self, system: str, user: str) -> str:
        data = self._post({
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": self.max_tokens, "responseMimeType": "application/json"},
        })
        self.resolved_model = data.get("modelVersion") or self.resolved_model
        if (data.get("promptFeedback") or {}).get("blockReason"):
            raise LLMError("model declined the request")
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError("model returned no text")
        reason = candidates[0].get("finishReason")
        if reason == "MAX_TOKENS":
            raise LLMError("model output was truncated")
        if reason in {"SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST"}:
            raise LLMError("model declined the request")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        if not text:
            raise LLMError("model returned no text")
        return text


def default_client() -> LLMClient:
    """Gemini if a Gemini key is set (free tier), otherwise Claude."""
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return GeminiClient()
    return AnthropicClient()
