"""Agent 4 takes the scheme records the rest of the pipeline produces."""
import pytest
from pydantic import BaseModel

from agent4 import (CalendarRequest, EmailRequest, SchemeContext, analyse_rejection,
                    build_calendar_artifact, build_email_draft)


class OtherRecord(BaseModel):
    """Stand-in for any pydantic record with extra fields (no member2 import)."""
    id: str = "demo_obj"
    name: str = "Demo Object Scheme"
    official_sources: list[str] = ["https://example.gov.in/obj"]
    deadline: str = "2026-12-20"
    deadline_source_url: str = "https://example.gov.in/obj/notice"
    requirements: list = []


@pytest.mark.parametrize("scheme", [OtherRecord(), OtherRecord().model_dump()])
def test_all_entry_points_accept_objects_and_dicts(scheme):
    assert SchemeContext.model_validate(scheme).id == "demo_obj"
    assert EmailRequest(scheme=scheme, question="Q?").scheme.name == "Demo Object Scheme"
    assert build_email_draft({"scheme": scheme, "question": "When are results announced?"}).status.value == "ready"
    cal = build_calendar_artifact(CalendarRequest(scheme=scheme))
    assert cal.status.value == "ready" and "DTSTART;VALUE=DATE:20261220" in cal.body_content
    assert analyse_rejection(scheme, "Rejected.").supported is False


def test_member2_scheme_record_is_accepted():
    member2_models = pytest.importorskip("member2.models")
    rec = member2_models.SchemeRecord(id="demo_m2", name="Demo M2 Scheme", official_sources=["https://example.gov.in/m2"])
    assert build_email_draft({"scheme": rec, "question": "Q?"}).title == "Email draft: Demo M2 Scheme"
