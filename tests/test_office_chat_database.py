"""Unit tests for Office Chat Simulator SQLite persistence in api/database.py."""
import tempfile
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
import pytest

from agent4.office_chat_models import (
    AppointmentOffer,
    AppointmentStatus,
    ChatStatus,
    ContactSource,
    OfficeChatMessage,
    OfficeChatSession,
    OfficeContact,
    TimeWindow,
    UnresolvedQuestion,
    UnresolvedQuestionStatus,
    UserAppointmentPreferences,
    VerificationStatus,
)
from api.database import (
    add_office_chat_message,
    create_office_chat_session,
    create_session,
    create_unresolved_question,
    get_appointment_preferences,
    get_office_chat_session,
    get_office_contact,
    get_office_contact_by_scheme,
    get_unresolved_question,
    init_db,
    list_office_chat_messages,
    list_office_chat_sessions,
    list_unresolved_questions,
    save_appointment_preferences,
    save_office_contact,
    update_office_chat_session,
    update_unresolved_question,
)


@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test_office_chat.db"
    return str(db_file)


@pytest.mark.asyncio
async def test_office_contact_persistence(temp_db):
    await init_db(db_path=temp_db)

    contact = OfficeContact(
        office_id="office_test_01",
        scheme_id="scheme_ssp_01",
        office_name="Social Welfare Department",
        office_address="5th Floor, M.S. Building, Bengaluru",
        office_hours={"monday": {"open": "10:00", "close": "17:30"}, "timezone": "Asia/Kolkata"},
        whatsapp_number="+918277712345",
        email="help@karnataka.gov.in",
        reception_number="080-22634300",
        source_url="https://ssp.postmatric.karnataka.gov.in",
        contact_source=ContactSource.website,
        verification_status=VerificationStatus.verified,
        last_checked=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
    )

    saved = await save_office_contact(contact, db_path=temp_db)
    assert saved.office_id == "office_test_01"

    # Fetch by ID
    loaded = await get_office_contact("office_test_01", db_path=temp_db)
    assert loaded is not None
    assert loaded.office_name == "Social Welfare Department"
    assert loaded.whatsapp_number == "+918277712345"
    assert loaded.office_hours["timezone"] == "Asia/Kolkata"
    assert loaded.verification_status == VerificationStatus.verified

    # Fetch by Scheme
    loaded_scheme = await get_office_contact_by_scheme("scheme_ssp_01", db_path=temp_db)
    assert loaded_scheme is not None
    assert loaded_scheme.office_id == "office_test_01"


@pytest.mark.asyncio
async def test_appointment_preferences_persistence(temp_db):
    await init_db(db_path=temp_db)
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    await create_session(session_id=session_id, context={}, db_path=temp_db)

    prefs = UserAppointmentPreferences(
        preference_id="pref_01",
        session_id=session_id,
        scheme_id="scheme_ssp_01",
        office_id="office_test_01",
        preferred_days=["monday", "wednesday"],
        preferred_windows=[TimeWindow(start="10:00", end="12:30"), TimeWindow(start="14:00", end="16:00")],
        date_range_start=date(2026, 11, 2),
        date_range_end=date(2026, 11, 15),
        pre_authorized_confirmation=True,
    )

    await save_appointment_preferences(prefs, db_path=temp_db)

    loaded = await get_appointment_preferences(session_id, scheme_id="scheme_ssp_01", db_path=temp_db)
    assert loaded is not None
    assert loaded.preference_id == "pref_01"
    assert loaded.preferred_days == ["monday", "wednesday"]
    assert len(loaded.preferred_windows) == 2
    assert loaded.preferred_windows[0].start == "10:00"
    assert loaded.preferred_windows[1].end == "16:00"
    assert loaded.pre_authorized_confirmation is True
    assert loaded.date_range_start == date(2026, 11, 2)


@pytest.mark.asyncio
async def test_office_chat_session_lifecycle(temp_db):
    await init_db(db_path=temp_db)
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    await create_session(session_id=session_id, context={}, db_path=temp_db)

    chat_session = OfficeChatSession(
        chat_id="chat_test_01",
        session_id=session_id,
        scheme_id="scheme_ssp_01",
        office_id="office_test_01",
        scenario_id="scenario_a_success",
        simulation_mode=True,
        chat_status=ChatStatus.in_progress,
        appointment_status=AppointmentStatus.offered,
        appointment=AppointmentOffer(date="2026-11-02", time="11:00", status=AppointmentStatus.offered),
    )

    await create_office_chat_session(chat_session, db_path=temp_db)

    loaded = await get_office_chat_session("chat_test_01", db_path=temp_db)
    assert loaded is not None
    assert loaded.chat_id == "chat_test_01"
    assert loaded.chat_status == ChatStatus.in_progress
    assert loaded.appointment_status == AppointmentStatus.offered
    assert loaded.appointment.date == "2026-11-02"

    # Update state to simulated_confirmed
    loaded.chat_status = ChatStatus.completed
    loaded.appointment_status = AppointmentStatus.simulated_confirmed
    loaded.appointment.status = AppointmentStatus.simulated_confirmed
    loaded.completed_at = datetime.now(timezone.utc)

    await update_office_chat_session(loaded, db_path=temp_db)

    reloaded = await get_office_chat_session("chat_test_01", db_path=temp_db)
    assert reloaded.chat_status == ChatStatus.completed
    assert reloaded.appointment_status == AppointmentStatus.simulated_confirmed
    assert reloaded.completed_at is not None

    # List by session
    all_chats = await list_office_chat_sessions(session_id, db_path=temp_db)
    assert len(all_chats) == 1
    assert all_chats[0].chat_id == "chat_test_01"


@pytest.mark.asyncio
async def test_office_chat_messages_ordering(temp_db):
    await init_db(db_path=temp_db)

    msg1 = OfficeChatMessage(
        chat_id="chat_01",
        sender="unlocked",
        message_text="Hello, inquiring about document verification.",
        turn_index=1,
    )
    msg2 = OfficeChatMessage(
        chat_id="chat_01",
        sender="simulated_office",
        message_text="We have a slot on Monday at 11:00 AM.",
        turn_index=2,
    )

    await add_office_chat_message(msg1, db_path=temp_db)
    await add_office_chat_message(msg2, db_path=temp_db)

    messages = await list_office_chat_messages("chat_01", db_path=temp_db)
    assert len(messages) == 2
    assert messages[0].turn_index == 1
    assert messages[0].sender == "unlocked"
    assert messages[1].turn_index == 2
    assert messages[1].sender == "simulated_office"


@pytest.mark.asyncio
async def test_unresolved_question_lifecycle(temp_db):
    await init_db(db_path=temp_db)
    session_id = f"sess_{uuid.uuid4().hex[:8]}"

    uq = UnresolvedQuestion(
        question_id="uq_test_01",
        chat_id="chat_01",
        session_id=session_id,
        question_text="Please provide candidate admission reference number.",
        receiver_whatsapp_number="+919845012345",
        contact_source=ContactSource.receiver_provided,
        status=UnresolvedQuestionStatus.open,
    )

    await create_unresolved_question(uq, db_path=temp_db)

    loaded = await get_unresolved_question("uq_test_01", db_path=temp_db)
    assert loaded is not None
    assert loaded.receiver_whatsapp_number == "+919845012345"
    assert loaded.status == UnresolvedQuestionStatus.open

    # Update status and draft
    loaded.status = UnresolvedQuestionStatus.draft_prepared
    loaded.draft_message = "Hello, here is my admission reference number."
    loaded.click_to_chat_url = "https://wa.me/919845012345?text=Hello"
    await update_unresolved_question(loaded, db_path=temp_db)

    reloaded = await get_unresolved_question("uq_test_01", db_path=temp_db)
    assert reloaded.status == UnresolvedQuestionStatus.draft_prepared
    assert reloaded.draft_message == "Hello, here is my admission reference number."
    assert reloaded.click_to_chat_url == "https://wa.me/919845012345?text=Hello"

    all_uqs = await list_unresolved_questions(session_id, db_path=temp_db)
    assert len(all_uqs) == 1
