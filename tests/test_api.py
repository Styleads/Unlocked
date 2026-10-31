"""
tests/test_api.py — End-to-end HTTP integration tests for FastAPI REST API endpoints.

Tests health checks, session lifecycle, discovery pipeline, consolidated questions,
answer submission & reassessment, and document action plan DAG endpoints using httpx AsyncClient.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from api.database import init_db
from api.main import app


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path, monkeypatch):
    """Set temporary database path for API tests."""
    import asyncio
    db_file = tmp_path / "test_api.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    asyncio.run(init_db(str(db_file)))


@pytest.mark.asyncio
async def test_health_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "services" in data
        assert data["services"]["sqlite_connected"] is True

        res_api = await client.get("/api/health")
        assert res_api.status_code == 200
        assert res_api.json()["operational"] is True


@pytest.mark.asyncio
async def test_session_lifecycle_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Create session
        payload = {
            "context": {
                "occupation": "farmer",
                "state": "Karnataka",
                "district": "Mandya",
                "annual_income": 150000,
                "interests": ["crop insurance"],
            },
            "scope": "guided",
            "preferred_language": "en",
        }
        res = await client.post("/api/sessions", json=payload)
        assert res.status_code == 201
        session_info = res.json()
        session_id = session_info["session_id"]
        assert session_info["status"] == "initialized"

        # 2. Retrieve session state
        res_get = await client.get(f"/api/sessions/{session_id}")
        assert res_get.status_code == 200
        state = res_get.json()
        assert state["session_id"] == session_id
        assert state["state_status"] == "CONTEXT_INITIALIZED"
        assert "annual_family_income" in state["answers"]
        assert state["answers"]["annual_family_income"]["value"] == {"min": 150000.0, "max": 150000.0}

        # 3. Delete session
        res_del = await client.delete(f"/api/sessions/{session_id}")
        assert res_del.status_code == 200
        assert res_del.json()["deleted"] is True

        # 4. Verify 404 after deletion
        res_gone = await client.get(f"/api/sessions/{session_id}")
        assert res_gone.status_code == 404


@pytest.mark.asyncio
async def test_full_discovery_questionnaire_and_reassessment_flow():
    """
    Simulates complete Review Round 1 user journey:
    Context -> Discovery -> Consolidated Questions -> Answer Submission -> Reassessment.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Create session
        res_sess = await client.post(
            "/api/sessions",
            json={
                "context": {
                    "occupation": "farmer",
                    "state": "Karnataka",
                    "district": "Mandya",
                    "annual_income": 150000,
                },
                "scope": "guided",
                "preferred_language": "en",
            },
        )
        assert res_sess.status_code == 201
        session_id = res_sess.json()["session_id"]

        # Step 2: Run discovery
        res_disc = await client.post(
            f"/api/sessions/{session_id}/discover",
            json={"search_scope": "fallback", "enable_fallback": True},
        )
        assert res_disc.status_code == 200
        disc_data = res_disc.json()
        assert disc_data["status"] == "discovery_complete"
        assert disc_data["total_schemes"] >= 4
        assert len(disc_data["schemes"]) >= 4

        # Step 3: Fetch schemes and single scheme
        res_schemes = await client.get(f"/api/sessions/{session_id}/schemes")
        assert res_schemes.status_code == 200
        schemes = res_schemes.json()
        first_scheme_id = schemes[0]["id"]

        res_single = await client.get(f"/api/sessions/{session_id}/schemes/{first_scheme_id}")
        assert res_single.status_code == 200
        assert res_single.json()["id"] == first_scheme_id

        # Step 4: Fetch consolidated questions
        res_q = await client.get(f"/api/sessions/{session_id}/questions")
        assert res_q.status_code == 200
        questions = res_q.json()
        assert isinstance(questions, list)

        # Step 5: Phase 4 Answer submission and non-destructive skip
        res_ans = await client.post(
            f"/api/sessions/{session_id}/answers",
            json={
                "answers": [
                    {"attribute": "gender", "value": "Female", "state": "answered"},
                    {"attribute": "is_minority", "state": "unknown"},  # Citizen said "not sure"
                ]
            },
        )
        assert res_ans.status_code == 200
        reassessment = res_ans.json()
        assert reassessment["status"] == "reassessed"
        assert len(reassessment["assessments"]) >= 4

        # Step 6: Verify unknown answer did not cause failure
        res_state = await client.get(f"/api/sessions/{session_id}")
        state = res_state.json()
        assert state["state_status"] == "ASSESSMENT_UPDATED"
        assert state["answers"]["is_minority"]["state"] == "unknown"


@pytest.mark.asyncio
async def test_action_plan_dag_and_checklist_update():
    """
    Test Phase 5 endpoints:
    Retrieving topological document DAG and toggling checklist status.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create session and run discovery
        res_sess = await client.post(
            "/api/sessions",
            json={"context": {"state": "Karnataka"}, "scope": "all"},
        )
        session_id = res_sess.json()["session_id"]

        await client.post(
            f"/api/sessions/{session_id}/discover",
            json={"search_scope": "fallback", "enable_fallback": True},
        )

        # 1. Fetch action plan
        res_plan = await client.get(f"/api/sessions/{session_id}/plan")
        assert res_plan.status_code == 200
        plan = res_plan.json()
        assert len(plan["checklist"]) > 0
        assert len(plan["nodes"]) > 0
        assert len(plan["edges"]) > 0

        first_doc = plan["checklist"][0]
        doc_id = first_doc["id"]

        # 2. Update status of document to "obtained"
        res_update = await client.post(
            f"/api/sessions/{session_id}/checklist/{doc_id}",
            json={"status": "obtained"},
        )
        assert res_update.status_code == 200
        updated_plan = res_update.json()

        # Confirm status updated in checklist
        updated_item = next((item for item in updated_plan["checklist"] if item["id"] == doc_id), None)
        assert updated_item is not None
        assert updated_item["status"] == "obtained"


@pytest.mark.asyncio
async def test_api_404_handling():
    """Verify clean 404 responses for non-existent session IDs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fake_id = "00000000-0000-0000-0000-000000000000"

        assert (await client.get(f"/api/sessions/{fake_id}")).status_code == 404
        assert (await client.delete(f"/api/sessions/{fake_id}")).status_code == 404
        assert (await client.post(f"/api/sessions/{fake_id}/discover")).status_code == 404
        assert (await client.get(f"/api/sessions/{fake_id}/schemes")).status_code == 404
        assert (await client.get(f"/api/sessions/{fake_id}/questions")).status_code == 404
        assert (await client.post(f"/api/sessions/{fake_id}/answers", json={"answers": []})).status_code == 404
        assert (await client.get(f"/api/sessions/{fake_id}/plan")).status_code == 404


@pytest.mark.asyncio
async def test_kannada_discovery_endpoint():
    """Verify discovery endpoint returns Kannada translated schemes when requested."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res_sess = await client.post(
            "/api/sessions",
            json={"context": {"state": "Karnataka", "occupation": "farmer"}, "preferred_language": "kn"},
        )
        session_id = res_sess.json()["session_id"]

        res_disc = await client.post(
            f"/api/sessions/{session_id}/discover",
            json={"search_scope": "fallback", "preferred_language": "kn", "enable_fallback": True},
        )
        assert res_disc.status_code == 200
        data = res_disc.json()
        assert data["preferred_language"] == "kn"
        assert data["translation_status"] == "complete"
        first_title = data["schemes"][0]["name"]
        assert any("\u0c80" <= c <= "\u0cff" for c in first_title)

