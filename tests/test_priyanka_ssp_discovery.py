"""
tests/test_priyanka_ssp_discovery.py — End-to-end test of Priyanka Naik's scenario.
"""
import os
import tempfile
import pytest

from api.database import create_session, init_db
from api.orchestrator import (
    generate_action_plan,
    generate_calendar_action,
    get_session_questions,
    get_session_schemes,
    run_discovery,
)
from api.schemas import EventKind, SessionCalendarActionRequest


@pytest.mark.asyncio
async def test_priyanka_naik_ssp_discovery_and_eligibility():
    """
    Verify that Priyanka Naik (SC Engineering student, Dharwad, ₹1.8L income):
    1. Matches the Karnataka SSP Post-Matric Scholarship for SC/ST and Fee Reimbursement.
    2. Status is POTENTIAL_MATCH (not unlikely_to_match, not not_yet_verified).
    3. Is NOT asked if she lives in Karnataka or from Karnataka.
    4. Receives a structured DAG document action plan including Nadakacheri RD numbers,
       Kutumba ID, Aadhaar DBT, UUCMS ID, and e-Attestation ID.
    5. Has verified deadline and can generate a calendar .ics action.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        await init_db(db_path)
        ctx = {
            "name": "Priyanka Naik",
            "occupation": "student",
            "state": "Karnataka",
            "district": "Dharwad",
            "annual_income": 180000,
            "education_level": "Undergraduate",
            "course_type": "Engineering",
            "social_category": "SC",
            "interests": ["post-matric scholarship", "fee reimbursement", "hostel subsidy"],
            "domicile_karnataka": True,
        }

        # 1. Create session
        session = await create_session("priyanka-test", ctx, db_path=db_path)
        assert session.answers.get("state").value == "Karnataka"
        assert session.answers.get("district").value == "Dharwad"
        assert session.answers.get("domicile_karnataka").value is True
        assert session.answers.get("social_category").value == "SC"

        # 2. Run discovery (fallback mode for offline determinism)
        disc_res = await run_discovery("priyanka-test", search_scope="fallback", db_path=db_path)
        assert disc_res.total_schemes >= 1

        schemes = await get_session_schemes("priyanka-test", db_path=db_path)
        ssp_scheme = next((s for s in schemes if "fallback-ssp-scst-001" in s.id or "Post-Matric" in s.name), None)
        assert ssp_scheme is not None, f"SSP scheme not found in {schemes}"

        # 3. Assessment status must be POTENTIAL_MATCH
        assert ssp_scheme.assessment_status == "potential_match", (
            f"Expected potential_match but got {ssp_scheme.assessment_status}: {ssp_scheme.assessment_explanation}"
        )
        assert "appear to meet" in ssp_scheme.assessment_explanation

        # Check deadline is present
        assert ssp_scheme.deadline == "2026-12-31"

        # 4. Check questions — MUST NOT ask about Karnataka
        questions = await get_session_questions("priyanka-test", db_path=db_path)
        for q in questions:
            assert q.attribute != "state"
            assert q.attribute != "domicile_karnataka"
            assert "karnataka" not in q.attribute.lower()
            assert "karnataka" not in q.question.lower()

        # 5. Check Action Plan DAG
        plan = await generate_action_plan("priyanka-test", db_path=db_path)
        doc_names = [item.name for item in plan.checklist]
        assert any("Aadhaar" in d for d in doc_names)
        assert any("Caste" in d for d in doc_names)
        assert any("Income" in d for d in doc_names)
        assert any("Kutumba" in d for d in doc_names)
        assert any("Attestation" in d for d in doc_names)

        # 6. Calendar action for SSP deadline
        cal_action = await generate_calendar_action(
            "priyanka-test",
            SessionCalendarActionRequest(
                scheme_id=ssp_scheme.id,
                kind=EventKind.deadline,
                event_date=ssp_scheme.deadline,
                date_confirmed_by_user=True,
            ),
            db_path=db_path,
        )
        assert cal_action.status == "ready" or getattr(cal_action.status, "value", None) == "ready"
        assert cal_action.body_content is not None
        assert "VCALENDAR" in cal_action.body_content
        assert "20261231" in cal_action.body_content
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
