"""
tests/test_orchestrator.py — Integration tests for Central Orchestrator (Phase 3).

Verifies the complete pipeline:
Context Seeding -> Discovery Execution -> Translation -> Schema Adapter ->
Normalization -> Assessment -> Consolidated Questions -> Answer Application ->
Reassessment -> Document Plan DAG -> SQLite Session Durability.
"""
import pytest
from pathlib import Path

from api.database import create_session, get_session, init_db
from api.orchestrator import (
    build_scheme_views,
    generate_action_plan,
    get_session_questions,
    get_session_scheme,
    get_session_schemes,
    process_answers,
    run_discovery,
    update_checklist_status,
)
from member2.models import (
    AnswerState,
    DocStatus,
    Requirement,
    RequirementVerification,
    SchemeRecord,
    SchemeStatus,
)


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a clean SQLite database path."""
    db_file = tmp_path / "test_orchestrator.db"
    return str(db_file)


@pytest.mark.asyncio
async def test_phase3_end_to_end_discovery_pipeline(temp_db_path):
    """
    Test Phase 3:
    1. Create session with Mandya farmer context.
    2. Run discovery in fallback mode.
    3. Verify M1 -> Adapter -> M2 Normalization -> M2 Assessment flow.
    4. Confirm complete persistence in SQLite.
    """
    await init_db(temp_db_path)

    farmer_context = {
        "occupation": "farmer",
        "state": "Karnataka",
        "district": "Mandya",
        "annual_income": 150000,
        "interests": ["crop insurance", "irrigation subsidy"],
    }

    # 1. Initialize session and seed context
    session = await create_session(
        session_id="sess-orch-001",
        context=farmer_context,
        scope="guided",
        preferred_language="en",
        db_path=temp_db_path,
    )
    assert session.state_status == "CONTEXT_INITIALIZED"
    assert "annual_family_income" in session.answers
    assert session.answers["annual_family_income"].state == AnswerState.answered

    # 2. Run Phase 3 Discovery
    result = await run_discovery(
        session_id="sess-orch-001",
        search_scope="fallback",
        enable_fallback=True,
        db_path=temp_db_path,
    )

    # 3. Assert discovery output
    assert result.session_id == "sess-orch-001"
    assert result.status == "discovery_complete"
    assert result.total_schemes >= 4
    assert result.source_mode == "fallback"
    assert len(result.schemes) == result.total_schemes
    assert len(result.assessments) == result.total_schemes

    # Check scheme views
    pmfby = next((s for s in result.schemes if "pmfby" in s.id.lower()), None)
    assert pmfby is not None
    assert pmfby.name != ""
    assert pmfby.assessment_status is not None
    assert len(pmfby.documents) > 0

    # 4. Check SQLite persistence durability
    persisted = await get_session("sess-orch-001", db_path=temp_db_path)
    assert persisted is not None
    assert persisted.state_status == "DISCOVERY_COMPLETE"
    assert len(persisted.normalized_schemes) == result.total_schemes
    assert len(persisted.assessments) == result.total_schemes


@pytest.mark.asyncio
async def test_phase3_discovery_with_kannada_translation(temp_db_path):
    """
    Test Phase 3 with Kannada translation:
    Verifies that Kannada overlay translation is invoked, authentic titles are returned,
    and metadata confirms translation_status='complete'.
    """
    await init_db(temp_db_path)

    session = await create_session(
        session_id="sess-orch-kn",
        context={"state": "Karnataka", "district": "Mysuru", "occupation": "farmer"},
        scope="all",
        preferred_language="kn",
        db_path=temp_db_path,
    )

    result = await run_discovery(
        session_id="sess-orch-kn",
        search_scope="fallback",
        preferred_language="kn",
        enable_fallback=True,
        db_path=temp_db_path,
    )

    assert result.preferred_language == "kn"
    assert result.translation_status == "complete"
    assert result.total_schemes >= 4

    # Check authentic Kannada title on first scheme
    kannada_scheme = result.schemes[0]
    # Check that title contains Kannada characters (range \u0C80-\u0CFF)
    has_kannada_char = any("\u0c80" <= char <= "\u0cff" for char in kannada_scheme.name)
    assert has_kannada_char, f"Expected Kannada text in {kannada_scheme.name}"


@pytest.mark.asyncio
async def test_question_answering_and_reassessment(temp_db_path):
    """
    Test submitting answers and reassessing schemes.
    """
    await init_db(temp_db_path)
    await create_session("sess-ans-flow", {"state": "Karnataka"}, db_path=temp_db_path)

    # Run discovery to populate schemes
    await run_discovery(
        session_id="sess-ans-flow",
        search_scope="fallback",
        enable_fallback=True,
        db_path=temp_db_path,
    )

    # Submit an answer and a "not sure" skip
    reassess_res = await process_answers(
        session_id="sess-ans-flow",
        submitted_answers=[
            {"attribute": "gender", "value": "Female", "state": "answered"},
            {"attribute": "is_minority", "state": "unknown"},
        ],
        db_path=temp_db_path,
    )

    assert reassess_res.status == "reassessed"
    assert len(reassess_res.assessments) >= 4

    # Verify session state reflects answers
    session = await get_session("sess-ans-flow", db_path=temp_db_path)
    assert session.answers["gender"].value == "Female"
    assert session.answers["is_minority"].state == AnswerState.unknown


@pytest.mark.asyncio
async def test_document_action_plan_and_checklist_toggle(temp_db_path):
    """
    Test Action Plan DAG generation and checklist status update.
    """
    await init_db(temp_db_path)
    await create_session("sess-plan-flow", {"state": "Karnataka"}, db_path=temp_db_path)

    await run_discovery(
        session_id="sess-plan-flow",
        search_scope="fallback",
        enable_fallback=True,
        db_path=temp_db_path,
    )

    # 1. Generate plan
    plan = await generate_action_plan("sess-plan-flow", db_path=temp_db_path)
    assert plan is not None
    assert len(plan.checklist) > 0
    assert len(plan.nodes) > 0
    assert len(plan.edges) > 0
    first_item = plan.checklist[0]

    # 2. Update status of the first document to "obtained"
    updated_plan = await update_checklist_status(
        session_id="sess-plan-flow",
        doc_id=first_item.id,
        status=DocStatus.obtained,
        db_path=temp_db_path,
    )

    # Check updated plan preserves item and reflects status
    item_updated = next((c for c in updated_plan.checklist if c.id == first_item.id), None)
    assert item_updated is not None
    assert item_updated.status == DocStatus.obtained


@pytest.mark.asyncio
async def test_run_discovery_non_existent_session_raises(temp_db_path):
    await init_db(temp_db_path)
    with pytest.raises(KeyError):
        await run_discovery("non-existent-session-id", db_path=temp_db_path)

