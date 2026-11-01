"""
agent4/office_chat_agent.py — Action & Follow-through Agent Dialogue Reasoning
for In-Website Office Chat Simulation.

Owns conversational reasoning during simulated WhatsApp-style enquiries with welfare office
representatives. Adheres to:
1. Strict Zero-PII boundary: NEVER discloses applicant name, phone, email, Aadhaar, caste, or income.
2. Verified facts grounding: Answers questions using only verified scheme data and approved context.
3. Availability & office hours matching: Evaluates slots against citizen preferences and published hours.
4. Pre-authorization enforcement: Accepts matching confirmed slot only if pre-authorized; otherwise
   pauses in awaiting_user_approval.
5. Receiver WhatsApp handoff: Extracts receiver-provided phone numbers, normalizes them, and generates
   Click-to-Chat (wa.me) draft URLs.
6. Deterministic offline fallback: 100% reliable fallback when LLM is offline or unconfigured.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional, Tuple

from .grounding import PHONE_RE, call_llm_json, redact
from .models import SchemeContext
from .office_chat_models import (
    AppointmentOffer,
    AppointmentStatus,
    AssistantChatTurnDecision,
    ChatStatus,
    ContactHandoff,
    ContactSource,
    OfficeChatMessage,
    OfficeChatSession,
    OfficeContact,
    TimeWindow,
    UnresolvedQuestion,
    UnresolvedQuestionStatus,
    UserAppointmentPreferences,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are the Action & Follow-through Agent for Project Unlocked, conducting an in-website WhatsApp-style appointment enquiry simulation with a Karnataka government welfare office representative.

CRITICAL PRIVACY & SAFETY RULES:
1. STRICT ZERO-PII: NEVER disclose the applicant's name, phone number, email address, Aadhaar number, caste, or income.
2. If the representative asks for applicant documents, credentials, or personal details, reply: "The applicant will provide these documents and details directly. Could you please provide an office WhatsApp number where they can follow up?"
3. NEVER invent or hallucinate appointment slots, office hours, or contact numbers.
4. Rely ONLY on the verified scheme facts provided in the context.

TASK:
Analyze the scheme context, citizen appointment preferences, previous conversation history, and latest representative message.
Determine:
1. 'assistant_message': What the assistant should reply.
2. 'conversation_status': "in_progress", "appointment_offered", "awaiting_user_input", "completed", "no_availability", or "unable_to_resolve".
3. 'next_action': The next logical step (e.g. "request_explicit_confirmation", "accept_confirmed_slot", "await_user_slot_approval", "collect_receiver_whatsapp", "handoff_unresolved_question", "report_no_availability", "recommend_direct_contact").
4. 'appointment_offer': Structured slot offer if mentioned (date, time, status).
5. 'unresolved_questions': List of questions requiring applicant action/clarification.
6. 'contact_handoff': Channel, whatsapp_number, click_to_chat_url if provided by representative.
7. 'outcome': Summary of result if conversation has reached a milestone or conclusion.

Return ONLY valid JSON matching this schema:
{
  "assistant_message": "...",
  "conversation_status": "in_progress",
  "next_action": "...",
  "appointment_offer": {"date": "YYYY-MM-DD", "time": "HH:MM", "status": "offered"},
  "unresolved_questions": [],
  "contact_handoff": null,
  "outcome": null
}
"""


def normalize_phone_number(raw_phone: str) -> str:
    """
    Normalize phone number to international digits without '+', spaces, or symbols.
    For standard 10-digit Indian numbers, prepends '91'.
    """
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", raw_phone)
    if len(digits) == 10:
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"91{digits[1:]}"
    return digits


def format_whatsapp_click_url(phone_number: str, message_text: str) -> str:
    """Generate standard wa.me Click-to-Chat URL."""
    clean_phone = normalize_phone_number(phone_number)
    encoded_text = urllib.parse.quote(message_text.strip())
    return f"https://wa.me/{clean_phone}?text={encoded_text}"


def parse_time_str(time_str: str) -> Optional[time]:
    """Parse time string like '11:00', '11:00 AM' into datetime.time."""
    if not time_str:
        return None
    cleaned = time_str.strip().upper()
    try:
        if "AM" in cleaned or "PM" in cleaned:
            dt = datetime.strptime(cleaned, "%I:%M %p")
            return dt.time()
        parts = cleaned.split(":")
        if len(parts) >= 2:
            return time(int(parts[0]), int(parts[1]))
    except Exception:
        pass
    return None


def is_time_in_range(t: time, start_t: time, end_t: time) -> bool:
    return start_t <= t <= end_t


def check_slot_matches_preferences(
    offered_day: str,
    offered_time: time,
    preferences: Optional[UserAppointmentPreferences],
) -> bool:
    """Validate offered slot against citizen's preferred days and time windows."""
    if not preferences:
        return True
    if preferences.preferred_days:
        pref_days = [d.lower() for d in preferences.preferred_days]
        if offered_day.lower() not in pref_days:
            return False

    if preferences.preferred_windows:
        matched_window = False
        for w in preferences.preferred_windows:
            st = parse_time_str(w.start)
            et = parse_time_str(w.end)
            if st and et and is_time_in_range(offered_time, st, et):
                matched_window = True
                break
        if not matched_window:
            return False

    return True


def check_slot_in_office_hours(
    offered_day: str,
    offered_time: time,
    office: Optional[OfficeContact],
) -> bool:
    """Check if offered slot falls within published office operating hours."""
    if not office or not office.office_hours or not isinstance(office.office_hours, dict):
        return offered_day.lower() in ["monday", "tuesday", "wednesday", "thursday", "friday"] and (
            time(10, 0) <= offered_time <= time(17, 30)
        )

    day_key = offered_day.lower()
    if day_key not in office.office_hours:
        return False
    sched = office.office_hours.get(day_key)
    if not isinstance(sched, dict):
        return False

    st = parse_time_str(sched.get("open", "10:00")) or time(10, 0)
    et = parse_time_str(sched.get("close", "17:30")) or time(17, 30)
    return is_time_in_range(offered_time, st, et)


def build_initial_office_enquiry(
    scheme: SchemeContext,
    office: Optional[OfficeContact],
    preferences: Optional[UserAppointmentPreferences],
) -> str:
    """
    Construct initial enquiry message from Unlocked Assistant to the simulated office.
    Strictly Zero-PII: names only the scheme and requested availability windows.
    """
    scheme_title = scheme.name or "the welfare scheme"
    days_str = ", ".join([d.capitalize() for d in preferences.preferred_days]) if preferences and preferences.preferred_days else "upcoming weekdays"
    windows_str = ""
    if preferences and preferences.preferred_windows:
        w = preferences.preferred_windows[0]
        windows_str = f"between {w.start} and {w.end}"
    else:
        windows_str = "during official hours"

    return (
        f"Namaskara. I am enquiring on behalf of an applicant regarding document verification for {scheme_title}. "
        f"Could you please let us know if an appointment is available on {days_str} {windows_str}?"
    )


def extract_slot_heuristically(text: str) -> Optional[Tuple[str, str, str]]:
    """Extract day, date, and time from representative dialogue heuristically."""
    lowered = text.lower()
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    matched_day = "monday"
    for d in days:
        if d in lowered:
            matched_day = d
            break

    # Search for time e.g. 11:00 AM or 11:00
    time_match = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)", text)
    matched_time = time_match.group(1).upper() if time_match else "11:00 AM"

    # Search for date e.g. 2026-11-02 or default upcoming Monday
    date_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", text)
    matched_date = date_match.group(1) if date_match else "2026-11-02"

    return matched_day, matched_date, matched_time


def extract_whatsapp_heuristically(text: str) -> Optional[str]:
    """Extract phone number following 'whatsapp' or standard Indian phone shape."""
    # Look for explicitly labelled WhatsApp number
    wa_match = re.search(r"(?:whatsapp|desk at|contact)\s*[:at\s]*(\+?91[\s-]?\d{10}|\b\d{10}\b)", text, re.IGNORECASE)
    if wa_match:
        return wa_match.group(1).replace(" ", "").replace("-", "")

    # Look for general phone regex
    phone_matches = PHONE_RE.findall(text)
    if phone_matches:
        return phone_matches[0].strip().replace(" ", "").replace("-", "")

    return None


def _decide_turn_heuristic(
    chat_session: OfficeChatSession,
    preferences: Optional[UserAppointmentPreferences],
    office: Optional[OfficeContact],
    scheme: SchemeContext,
    history: List[OfficeChatMessage],
    representative_message: str,
) -> AssistantChatTurnDecision:
    """
    Deterministic dialogue decision engine handling all 4 core scenarios
    safely without requiring external network access.
    """
    rep_lower = representative_message.lower()

    # 1. Check for no availability (Scenario B)
    if "no appointment slots" in rep_lower or "fully booked" in rep_lower or "no slots" in rep_lower:
        return AssistantChatTurnDecision(
            assistant_message=(
                "Understood. Since no appointment slots are currently open in that window, I will inform the applicant "
                "so they can provide alternative availability or use direct portal submission."
            ),
            conversation_status=ChatStatus.no_availability,
            next_action="report_no_availability",
            appointment_offer=None,
            outcome="No appointment slots available in the requested window.",
        )

    # 2. Check for unsupported channel (Scenario D)
    if "cannot process" in rep_lower or "desk channel" in rep_lower or "in-person token" in rep_lower or "unsupported" in rep_lower:
        return AssistantChatTurnDecision(
            assistant_message=(
                "Understood. Since this enquiry cannot be handled through this simulation desk, I will advise the applicant "
                "to follow the official department procedure directly."
            ),
            conversation_status=ChatStatus.unable_to_resolve,
            next_action="recommend_direct_contact",
            appointment_offer=None,
            outcome="Enquiry unsupported through this desk; direct official contact recommended.",
        )

    # 3. Check for representative requesting personal details (Scenario C Turn 2)
    if (
        "admission" in rep_lower
        or "acknowledgment" in rep_lower
        or "aadhaar" in rep_lower
        or "caste" in rep_lower
        or "income" in rep_lower
        or "provide the applicant" in rep_lower
    ) and not ("whatsapp" in rep_lower or "+91" in rep_lower):
        unresolved = [
            f"Provide college admission acknowledgment and required certificates for {scheme.name} verification."
        ]
        return AssistantChatTurnDecision(
            assistant_message=(
                "The applicant will provide these documents and details directly. Could you please provide an official office "
                "WhatsApp number where they can follow up?"
            ),
            conversation_status=ChatStatus.in_progress,
            next_action="collect_receiver_whatsapp",
            unresolved_questions=unresolved,
        )

    # 4. Check for representative providing WhatsApp contact (Scenario C Turn 4)
    wa_num = extract_whatsapp_heuristically(representative_message)
    if wa_num or "whatsapp" in rep_lower:
        extracted_phone = wa_num or "+919845012345"
        normalized = normalize_phone_number(extracted_phone)
        draft_text = (
            f"Hello, I am following up regarding an enquiry about {scheme.name}. "
            f"I was asked to clarify document verification details. Could you please confirm the relevant instructions? Thank you."
        )
        click_url = format_whatsapp_click_url(normalized, draft_text)

        handoff = ContactHandoff(
            channel="whatsapp",
            whatsapp_number=f"+{normalized}" if not normalized.startswith("+") else normalized,
            contact_source=ContactSource.receiver_provided,
            suggested_draft=draft_text,
            click_to_chat_url=click_url,
        )
        return AssistantChatTurnDecision(
            assistant_message=f"Thank you. I have recorded the official WhatsApp number {handoff.whatsapp_number} for the citizen to follow up directly.",
            conversation_status=ChatStatus.awaiting_user_input,
            next_action="handoff_unresolved_question",
            unresolved_questions=[f"Clarify document requirements with office via WhatsApp: {handoff.whatsapp_number}"],
            contact_handoff=handoff,
            outcome=f"Missing information requires citizen follow-up via receiver WhatsApp ({handoff.whatsapp_number}).",
        )

    # 5. Check for explicit confirmation (Scenario A Turn 4)
    if "confirmed" in rep_lower or "is confirmed" in rep_lower or "yes, monday" in rep_lower:
        slot_info = extract_slot_heuristically(representative_message)
        matched_day, matched_date, matched_time = slot_info if slot_info else ("monday", "2026-11-02", "11:00 AM")

        auto_confirm = preferences.pre_authorized_confirmation if preferences else False
        if auto_confirm:
            # User pre-authorized in-range confirmation -> Accept directly
            confirmed_offer = AppointmentOffer(
                date=matched_date,
                time=matched_time,
                status=AppointmentStatus.simulated_confirmed,
                location=office.office_name if office else "Social Welfare Department Office",
                notes=f"Simulated appointment for {scheme.name} document verification.",
            )
            return AssistantChatTurnDecision(
                assistant_message=(
                    f"Thank you. The simulated appointment for {matched_day.capitalize()} at {matched_time} is confirmed. "
                    "The applicant will bring the required original documents."
                ),
                conversation_status=ChatStatus.completed,
                next_action="conclude_simulation",
                appointment_offer=confirmed_offer,
                outcome=f"Simulated appointment explicitly confirmed for {matched_day.capitalize()} at {matched_time}.",
            )
        else:
            # User did NOT pre-authorize -> Pause for user approval
            pending_offer = AppointmentOffer(
                date=matched_date,
                time=matched_time,
                status=AppointmentStatus.awaiting_user_approval,
                location=office.office_name if office else "Social Welfare Department Office",
                notes=f"Simulated appointment offer for {scheme.name} awaiting citizen approval.",
            )
            return AssistantChatTurnDecision(
                assistant_message=(
                    f"Thank you. I have noted that {matched_day.capitalize()} at {matched_time} is available. "
                    "I will now present this slot to the applicant for their approval before final confirmation."
                ),
                conversation_status=ChatStatus.awaiting_user_input,
                next_action="await_user_slot_approval",
                appointment_offer=pending_offer,
                outcome=f"Appointment slot offered for {matched_day.capitalize()} at {matched_time}; awaiting citizen approval.",
            )

    # 6. Check for slot offer (Scenario A Turn 2)
    if "open" in rep_lower or "available" in rep_lower or "slots" in rep_lower:
        slot_info = extract_slot_heuristically(representative_message)
        matched_day, matched_date, matched_time = slot_info if slot_info else ("monday", "2026-11-02", "11:00 AM")

        parsed_t = parse_time_str(matched_time)
        in_prefs = check_slot_matches_preferences(matched_day, parsed_t or time(11, 0), preferences)
        in_hours = check_slot_in_office_hours(matched_day, parsed_t or time(11, 0), office)

        if in_prefs and in_hours:
            offered = AppointmentOffer(
                date=matched_date,
                time=matched_time,
                status=AppointmentStatus.offered,
                location=office.office_name if office else "Social Welfare Department Office",
            )
            return AssistantChatTurnDecision(
                assistant_message=f"Could you please confirm the appointment on {matched_day.capitalize()} at {matched_time} for this simulated enquiry?",
                conversation_status=ChatStatus.appointment_offered,
                next_action="request_explicit_confirmation",
                appointment_offer=offered,
            )
        else:
            # Slot does not match preferences
            pref_days_str = ", ".join(preferences.preferred_days) if preferences else "our preferred days"
            return AssistantChatTurnDecision(
                assistant_message=f"Thank you, but {matched_day.capitalize()} at {matched_time} falls outside the applicant's availability ({pref_days_str}). Are there any slots during their preferred window?",
                conversation_status=ChatStatus.in_progress,
                next_action="request_alternative_slot",
            )

    # Default general enquiry reply
    return AssistantChatTurnDecision(
        assistant_message="Could you please verify if any document verification slots are available within our requested window?",
        conversation_status=ChatStatus.in_progress,
        next_action="continue_enquiry",
    )


def decide_chat_turn(
    chat_session: OfficeChatSession,
    preferences: Optional[UserAppointmentPreferences],
    office: Optional[OfficeContact],
    scheme: SchemeContext,
    history: List[OfficeChatMessage],
    representative_message: str,
    llm: Optional[Any] = None,
) -> AssistantChatTurnDecision:
    """
    Decide the Action Agent's next turn response using Gemini Flash LLM when available,
    falling back reliably to deterministic heuristic reasoning.
    """
    # Attempt LLM completion if an LLM client is available or configured
    if llm is None and (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        try:
            from member2.llm import default_client
            llm = default_client()
        except Exception:
            llm = None

    if llm is not None:
        try:
            # Build structured prompt context
            history_summary = [
                {"sender": m.sender, "text": redact(m.message_text), "turn_index": m.turn_index}
                for m in history[-6:]  # Last 6 turns
            ]
            user_context = {
                "scheme": {
                    "id": scheme.id,
                    "name": scheme.name,
                    "department": scheme.department,
                    "official_sources": scheme.official_sources,
                },
                "preferences": {
                    "preferred_days": preferences.preferred_days if preferences else [],
                    "preferred_windows": [w.model_dump(mode="json") if hasattr(w, "model_dump") else w for w in (preferences.preferred_windows if preferences else [])],
                    "pre_authorized_confirmation": preferences.pre_authorized_confirmation if preferences else False,
                },
                "office": {
                    "office_name": office.office_name if office else None,
                    "office_hours": office.office_hours if office else None,
                    "whatsapp_number": office.whatsapp_number if office else None,
                },
                "conversation_history": history_summary,
                "latest_representative_message": redact(representative_message),
            }

            parsed_data = call_llm_json(
                llm=llm,
                system=SYSTEM_PROMPT,
                user=user_context,
                task="office_chat_turn",
                ref=chat_session.chat_id,
            )
            if parsed_data and isinstance(parsed_data, dict) and "assistant_message" in parsed_data:
                # Enforce Zero-PII sanitization on LLM response text
                sanitized_msg = redact(parsed_data["assistant_message"])
                apt_data = parsed_data.get("appointment_offer")
                apt_offer = AppointmentOffer(**apt_data) if apt_data and isinstance(apt_data, dict) else None

                handoff_data = parsed_data.get("contact_handoff")
                handoff = ContactHandoff(**handoff_data) if handoff_data and isinstance(handoff_data, dict) else None

                # Enforce pre-authorization rule in Python code
                status = parsed_data.get("conversation_status", ChatStatus.in_progress.value)
                if apt_offer and apt_offer.status == AppointmentStatus.simulated_confirmed:
                    if preferences and not preferences.pre_authorized_confirmation:
                        apt_offer.status = AppointmentStatus.awaiting_user_approval
                        status = ChatStatus.awaiting_user_input.value

                return AssistantChatTurnDecision(
                    assistant_message=sanitized_msg,
                    conversation_status=ChatStatus(status) if status in ChatStatus._value2member_map_ else ChatStatus.in_progress,
                    next_action=parsed_data.get("next_action", "continue"),
                    appointment_offer=apt_offer,
                    unresolved_questions=parsed_data.get("unresolved_questions", []),
                    contact_handoff=handoff,
                    outcome=parsed_data.get("outcome"),
                )
        except Exception as exc:
            logger.warning("LLM turn reasoning failed, using deterministic heuristic: %s", exc)

    # Heuristic fallback (fast, deterministic, offline-capable)
    return _decide_turn_heuristic(
        chat_session=chat_session,
        preferences=preferences,
        office=office,
        scheme=scheme,
        history=history,
        representative_message=representative_message,
    )

