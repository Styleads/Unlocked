import json

import pytest

from agent4 import SchemeContext


class ScriptedLLM:
    """Returns canned responses in order; an Exception instance is raised."""

    def __init__(self, *responses):
        self.responses = list(responses) or ["{}"]
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        r = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r)

    def payload(self, call: int = 0) -> dict:
        return json.loads(self.calls[call][1])


@pytest.fixture
def llm_factory():
    return ScriptedLLM


@pytest.fixture
def scheme():
    # Fictional (CLAUDE.md non-negotiable 5).
    return SchemeContext(
        id="demo_scholarship_a",
        name="Demo Scholarship A",
        department="Demo Welfare Department",
        application_url="https://example.gov.in/apply",
        official_sources=["https://example.gov.in/guidelines"],
        deadline="2026-12-15",
        deadline_source_url="https://example.gov.in/notice",
        contact_email="helpdesk@example.gov.in",
        contact_email_source_url="https://example.gov.in/contact",
    )


@pytest.fixture
def unsourced_scheme():
    return SchemeContext(id="demo_b", name="Demo Fee Concession B", contact_email="someone@example.gov.in",
                         deadline="2026-12-01")
