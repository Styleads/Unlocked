"""
tests/test_database.py — Unit and integration tests for SQLite session persistence.

Tests init_db, create_session with context answer seeding, state machine
transitions, discovery update, answer update, action plan update, and session deletion.
"""
import os
import tempfile
import pytest
import pytest_asyncio
from pathlib import Path

from api.database import (
    init_db,
    create_session,
    get_session,
    update_discovery_results,
    update_answers_and_assessments,
    update_plan,
    update_user_documents,
    delete_session,
    list_sessions,
)
from api.schemas import UserProfileInput
from member2.models import (
    ActionPlan,
    Answer,
    AnswerState,
    Assessment,
    ChecklistItem,
    DocStatus,
    Question,
    RequirementResult,
    RequirementStatus,
    SchemeRecord,
    SchemeStatus,
)
from member2.questions import apply_answers


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a path to a clean temporary SQLite database."""
    db_file = tmp_path / "test_unlocked.db"
    return str(db_file)


@pytest.mark.asyncio
async def test_init_db_creates_tables(temp_db_path):
    await init_db(temp_db_path)
    assert Path(temp_db_path).exists()
    sessions = await list_sessions(db_path=temp_db_path)
    assert sessions == []


@pytest.mark.asyncio
async def test_create_session_and_seed_context_answers(temp_db_path):
    await init_db(temp_db_path)

    profile = {
        "occupation": "farmer",
        "state": "Karnataka",
        "district": "Mandya",
        "annual_income": 150000,
        "interests": ["crop insurance"],
    }

    session = await create_session(
        session_id="session-123",
        context=profile,
        scope="guided",
        preferred_language="en",
        db_path=temp_db_path,
    )

    assert session.session_id == "session-123"
    assert session.state_status == "CONTEXT_INITIALIZED"
    assert session.scope == "guided"
    assert session.preferred_language == "en"

    # Verify context answer seeding
    assert "annual_family_income" in session.answers
    assert session.answers["annual_family_income"].state == AnswerState.answered
    assert session.answers["annual_family_income"].value == {"min": 150000.0, "max": 150000.0}

    assert "state" in session.answers
    assert session.answers["state"].value == "Karnataka"

    assert "district" in session.answers
    assert session.answers["district"].value == "Mandya"

    assert "employment_status" in session.answers
    assert session.answers["employment_status"].state == AnswerState.answered
    assert session.answers["employment_status"].value == "Self-employed"

    # Verify history tracking
    assert session.history.get("q_annual_family_income") == AnswerState.answered
    assert session.history.get("q_state") == AnswerState.answered
    assert session.history.get("q_district") == AnswerState.answered


@pytest.mark.asyncio
async def test_get_session_durability_and_deserialization(temp_db_path):
    await init_db(temp_db_path)

    session = await create_session(
        session_id="sess-persist-1",
        context={"state": "Karnataka", "district": "Mysuru"},
        scope="all",
        preferred_language="kn",
        db_path=temp_db_path,
    )

    # Re-fetch from SQLite
    restored = await get_session("sess-persist-1", db_path=temp_db_path)
    assert restored is not None
    assert restored.session_id == "sess-persist-1"
    assert restored.scope == "all"
    assert restored.preferred_language == "kn"
    assert restored.state_status == "CONTEXT_INITIALIZED"
    assert restored.answers["state"].value == "Karnataka"
    assert restored.history["q_state"] == AnswerState.answered


@pytest.mark.asyncio
async def test_update_discovery_results_flow(temp_db_path):
    await init_db(temp_db_path)
    await create_session("sess-disc", {"state": "Karnataka"}, db_path=temp_db_path)

    mock_scheme = SchemeRecord(
        id="karnataka-scheme-001",
        name="Karnataka Raitha Scheme",
        summary="Support for farmers",
        requirements=[],
        documents=[],
    )
    mock_assessment = Assessment(
        scheme_id="karnataka-scheme-001",
        status=SchemeStatus.potential_match,
        explanation="All criteria satisfied",
        requirements=[],
    )
    mock_question = Question(
        id="q_landholding",
        attribute="landholding",
        question="How much land do you own?",
        input_type="number",
        why_asked="Required for 1 scheme",
        sensitivity="low",
    )

    await update_discovery_results(
        session_id="sess-disc",
        raw_schemes=[{"name": "Raw Scheme"}],
        normalized_schemes=[mock_scheme],
        questions=[mock_question],
        assessments=[mock_assessment],
        db_path=temp_db_path,
    )

    restored = await get_session("sess-disc", db_path=temp_db_path)
    assert restored is not None
    assert restored.state_status == "DISCOVERY_COMPLETE"
    assert len(restored.normalized_schemes) == 1
    assert restored.normalized_schemes[0].id == "karnataka-scheme-001"
    assert len(restored.assessments) == 1
    assert restored.assessments[0].status == SchemeStatus.potential_match
    assert len(restored.questions) == 1
    assert restored.questions[0].id == "q_landholding"


@pytest.mark.asyncio
async def test_update_answers_and_assessments(temp_db_path):
    await init_db(temp_db_path)
    session = await create_session("sess-ans", {"state": "Karnataka"}, db_path=temp_db_path)

    # Submit an answer and a "not sure" skip
    new_answers, new_history = apply_answers(
        session.answers,
        session.history,
        [
            {"attribute": "gender", "value": "Female", "state": "answered"},
            {"attribute": "is_minority", "state": "unknown"},
        ],
    )

    updated_assessments = [
        Assessment(
            scheme_id="karnataka-scheme-001",
            status=SchemeStatus.more_information_needed,
            explanation="Minority status unknown",
        )
    ]

    await update_answers_and_assessments(
        session_id="sess-ans",
        answers=new_answers,
        history=new_history,
        assessments=updated_assessments,
        db_path=temp_db_path,
    )

    restored = await get_session("sess-ans", db_path=temp_db_path)
    assert restored is not None
    assert restored.state_status == "ASSESSMENT_UPDATED"
    assert restored.answers["gender"].value == "Female"
    assert restored.answers["is_minority"].state == AnswerState.unknown
    assert restored.history["q_is_minority"] == AnswerState.unknown
    assert restored.assessments[0].status == SchemeStatus.more_information_needed


@pytest.mark.asyncio
async def test_update_plan_and_checklist(temp_db_path):
    await init_db(temp_db_path)
    await create_session("sess-plan", {"state": "Karnataka"}, db_path=temp_db_path)

    mock_plan = ActionPlan(
        checklist=[
            ChecklistItem(
                id="doc_aadhaar",
                name="Aadhaar Card",
                status=DocStatus.have,
                order=1,
                reason="Needed first",
            ),
            ChecklistItem(
                id="doc_income",
                name="Income Certificate",
                status=DocStatus.needed,
                order=2,
                reason="Needed second",
            ),
        ],
        nodes=[],
        edges=[],
        shared_prerequisites=["doc_aadhaar"],
        explanation="Procure documents in order",
    )

    user_docs = {"doc_aadhaar": "have", "doc_income": "needed"}
    await update_plan("sess-plan", mock_plan, user_documents=user_docs, db_path=temp_db_path)

    restored = await get_session("sess-plan", db_path=temp_db_path)
    assert restored is not None
    assert restored.state_status == "PLAN_GENERATED"
    assert restored.plan is not None
    assert len(restored.plan.checklist) == 2
    assert restored.user_documents["doc_aadhaar"] == "have"
    assert restored.user_documents["doc_income"] == "needed"

    # Toggle doc status
    user_docs["doc_income"] = "obtained"
    await update_user_documents("sess-plan", user_docs, db_path=temp_db_path)
    restored2 = await get_session("sess-plan", db_path=temp_db_path)
    assert restored2.user_documents["doc_income"] == "obtained"


@pytest.mark.asyncio
async def test_delete_session(temp_db_path):
    await init_db(temp_db_path)
    await create_session("sess-del", {"state": "Karnataka"}, db_path=temp_db_path)

    assert await get_session("sess-del", db_path=temp_db_path) is not None
    deleted = await delete_session("sess-del", db_path=temp_db_path)
    assert deleted is True

    assert await get_session("sess-del", db_path=temp_db_path) is None
    deleted_again = await delete_session("sess-del", db_path=temp_db_path)
    assert deleted_again is False
