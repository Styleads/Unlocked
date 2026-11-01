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
    """Parse '11:00', '11:00 AM', '3 PM', '3PM', '3:00PM' into datetime.time; None when it can't be read."""
    if not time_str:
        return None
    cleaned = re.sub(r"\s+", " ", time_str.strip().upper())
    for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M"):
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            continue
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
    """Check an offered slot against published hours. Hours we don't have (none, or only a text note) rule nothing out."""
    hours = office.office_hours if office else None
    if not isinstance(hours, dict) or not any(isinstance(v, dict) for v in hours.values()):
        return True
    sched = hours.get(offered_day.lower())
    if not isinstance(sched, dict):
        return False
    st = parse_time_str(sched.get("open", ""))
    et = parse_time_str(sched.get("close", ""))
    if not st or not et:
        return True  # a day listed without readable times: unknown
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


_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_TIME_RE = re.compile(r"\b(\d{1,2}(?::\d{2})?\s*(?:AM|PM))\b|\b(\d{1,2}:\d{2})\b", re.IGNORECASE)


def extract_slot_heuristically(text: str) -> Optional[Tuple[str, Optional[str], str]]:
    """Day, date (if written as YYYY-MM-DD) and time named in a message. None unless both a day and a readable time are
    there: a slot the office did not state is never filled in."""
    lowered = (text or "").lower()
    day = next((d for d in _DAYS if re.search(rf"\b{d}\b", lowered)), None)
    m = _TIME_RE.search(text or "")
    when = (m.group(1) or m.group(2)).upper() if m else None
    if not day or not when or parse_time_str(when) is None:
        return None
    d = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text or "")
    return day, (d.group(1) if d else None), when


def _slot_from(rep_message: str, structured: Optional[dict]) -> Optional[Tuple[str, Optional[str], str]]:
    """The slot an office offered or confirmed: the simulator's structured data first, else what the message says."""
    if structured and isinstance(structured, dict):
        day = str(structured.get("day") or "").strip().lower()
        when = str(structured.get("time") or "").strip().upper()
        if day and parse_time_str(when) is not None:
            return day, (structured.get("date") or None), when
    return extract_slot_heuristically(rep_message)


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


def _says_no_availability(rep_lower: str) -> bool:
    return bool(re.search(r"\bno (?:appointment )?slots?\b|\bfully booked\b|\bnot available\b|\bunavailable\b|\bno availability\b", rep_lower))


def _says_unsupported(rep_lower: str) -> bool:
    return bool(re.search(r"\bcannot process\b|\bdesk channel\b|\bin-person token\b|\bunsupported\b", rep_lower))


def _says_confirmed(rep_lower: str) -> bool:
    """An explicit confirmation. 'not confirmed' and 'unconfirmed' are not one."""
    return bool(re.search(r"\bconfirmed\b", rep_lower)) and not re.search(r"\b(?:not|isn't|is not|cannot be|yet to be)\s+confirmed\b", rep_lower)


def _offers_slot(rep_lower: str) -> bool:
    return bool(re.search(r"\bavailable\b|\bslots?\b|\bopen\b", rep_lower)) and not _says_no_availability(rep_lower)


def _decide_turn_heuristic(
    chat_session: OfficeChatSession,
    preferences: Optional[UserAppointmentPreferences],
    office: Optional[OfficeContact],
    scheme: SchemeContext,
    history: List[OfficeChatMessage],
    representative_message: str,
    rep_result: Optional[Dict[str, Any]] = None,
) -> AssistantChatTurnDecision:
    """
    Deterministic dialogue decision engine for the four core scenarios. Everything it reports (status, slot, contact)
    comes from what the representative actually said, or from the simulator's structured version of it. It never fills
    in a slot, a time or a phone number that was not given.
    """
    rep = rep_result or {}
    rep_lower = representative_message.lower()
    office_name = (office.office_name if office and office.office_name else None) or "the office"

    # 1. No availability
    if _says_no_availability(rep_lower):
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

    # 2. Unsupported channel
    if _says_unsupported(rep_lower):
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

    # 3. The representative gives a WhatsApp number for the applicant to follow up on directly
    receiver_number = rep.get("receiver_whatsapp_number") or extract_whatsapp_heuristically(representative_message)
    normalized = normalize_phone_number(receiver_number) if receiver_number else ""
    if normalized and 10 <= len(normalized) <= 13:
        draft_text = (
            f"Hello, I am following up regarding an enquiry about {scheme.name}. "
            "I was asked to clarify document verification details. Could you please confirm the relevant instructions? Thank you."
        )
        handoff = ContactHandoff(
            channel="whatsapp",
            whatsapp_number=f"+{normalized}",
            contact_source=ContactSource.receiver_provided,
            suggested_draft=draft_text,
            # always built here from the number, never taken from model output
            click_to_chat_url=format_whatsapp_click_url(normalized, draft_text),
        )
        return AssistantChatTurnDecision(
            assistant_message=f"Thank you. I have recorded the WhatsApp number {handoff.whatsapp_number} for the applicant to follow up directly.",
            conversation_status=ChatStatus.awaiting_user_input,
            next_action="handoff_unresolved_question",
            unresolved_questions=[f"Follow up with the office on WhatsApp: {handoff.whatsapp_number}"],
            contact_handoff=handoff,
            outcome=f"Missing information needs the applicant to follow up on WhatsApp ({handoff.whatsapp_number}).",
        )
    if "whatsapp" in rep_lower:
        # mentioned, but no number: ask for it rather than make one up
        return AssistantChatTurnDecision(
            assistant_message="Could you please share the WhatsApp number the applicant should use?",
            conversation_status=ChatStatus.in_progress,
            next_action="collect_receiver_whatsapp",
        )

    # 4. The representative asks for the applicant's own details or documents
    asks_details = rep.get("intent") == "request_missing_info" or bool(
        re.search(r"\b(?:please provide|provide the applicant|acknowledg(?:e)?ment|aadhaar|admission)\b", rep_lower)
    )
    if asks_details:
        requested = rep.get("requested_info") or "the applicant's own details"
        return AssistantChatTurnDecision(
            assistant_message=(
                "The applicant will provide these documents and details directly. Could you please provide an official office "
                "WhatsApp number where they can follow up?"
            ),
            conversation_status=ChatStatus.in_progress,
            next_action="collect_receiver_whatsapp",
            unresolved_questions=[f"The office asked for: {requested}"],
        )

    # 5. Explicit confirmation of a slot
    if _says_confirmed(rep_lower):
        slot = _slot_from(representative_message, rep.get("confirmed_slot") or rep.get("offered_slot"))
        if slot is None:
            return AssistantChatTurnDecision(
                assistant_message="Thank you. Could you please repeat the day and time of the appointment so I can note it correctly?",
                conversation_status=ChatStatus.in_progress,
                next_action="clarify_slot",
            )
        day, slot_date, slot_time = slot
        t = parse_time_str(slot_time)
        usable = bool(t) and check_slot_matches_preferences(day, t, preferences) and check_slot_in_office_hours(day, t, office)
        pre_authorized = bool(preferences and preferences.pre_authorized_confirmation)
        if pre_authorized and usable:
            return AssistantChatTurnDecision(
                assistant_message=(
                    f"Thank you. The simulated appointment for {day.capitalize()} at {slot_time} is confirmed. "
                    "The applicant will bring the required original documents."
                ),
                conversation_status=ChatStatus.completed,
                next_action="conclude_simulation",
                appointment_offer=AppointmentOffer(
                    date=slot_date, time=slot_time, status=AppointmentStatus.simulated_confirmed,
                    location=office_name, notes=f"Simulated appointment for {scheme.name} document verification.",
                ),
                outcome=f"Simulated appointment explicitly confirmed for {day.capitalize()} at {slot_time}.",
            )
        # not pre-authorised, or outside what the applicant pre-authorised: it is the applicant's decision
        return AssistantChatTurnDecision(
            assistant_message=(
                f"Thank you. I have noted that {day.capitalize()} at {slot_time} is available. "
                + ("" if usable or not pre_authorized else "It is outside the times the applicant pre-approved, so ")
                + "I will now present this slot to the applicant for their approval before final confirmation."
            ),
            conversation_status=ChatStatus.awaiting_user_input,
            next_action="await_user_slot_approval",
            appointment_offer=AppointmentOffer(
                date=slot_date, time=slot_time, status=AppointmentStatus.awaiting_user_approval, location=office_name,
                notes=f"Simulated appointment offer for {scheme.name} awaiting citizen approval.",
            ),
            outcome=f"Appointment slot offered for {day.capitalize()} at {slot_time}; awaiting citizen approval.",
        )

    # 6. A slot is offered
    if _offers_slot(rep_lower):
        slot = _slot_from(representative_message, rep.get("offered_slot"))
        if slot is None:
            return AssistantChatTurnDecision(
                assistant_message="Thank you. Which day and time is the available slot?",
                conversation_status=ChatStatus.in_progress,
                next_action="clarify_slot",
            )
        day, slot_date, slot_time = slot
        t = parse_time_str(slot_time)
        if t and check_slot_matches_preferences(day, t, preferences) and check_slot_in_office_hours(day, t, office):
            return AssistantChatTurnDecision(
                assistant_message=f"Could you please confirm the appointment on {day.capitalize()} at {slot_time} for this simulated enquiry?",
                conversation_status=ChatStatus.appointment_offered,
                next_action="request_explicit_confirmation",
                appointment_offer=AppointmentOffer(date=slot_date, time=slot_time, status=AppointmentStatus.offered, location=office_name),
            )
        wanted = ", ".join(d.capitalize() for d in preferences.preferred_days) if preferences and preferences.preferred_days else "the applicant's availability"
        return AssistantChatTurnDecision(
            assistant_message=f"Thank you, but {day.capitalize()} at {slot_time} falls outside {wanted}. Is there another slot that fits?",
            conversation_status=ChatStatus.in_progress,
            next_action="request_alternative_slot",
        )

    return AssistantChatTurnDecision(
        assistant_message="Could you please verify if any document verification slots are available within our requested window?",
        conversation_status=ChatStatus.in_progress,
        next_action="continue_enquiry",
    )


REWORD_PROMPT = """You reword one message from Unlocked's assistant to a (simulated) welfare office desk.
Keep exactly the same meaning and every fact in it. Do not add facts, names, numbers, links, dates or times.
Never mention the applicant's name, phone, email, Aadhaar, caste or income. Keep it polite and under 60 words.
Return ONLY JSON: {"assistant_message": "..."}"""


def _reworded(llm: Any, original: str, chat_id: str) -> str:
    """Let the model only change the wording. Anything that adds a link or a figure the original didn't have is rejected."""
    try:
        out = call_llm_json(llm=llm, system=REWORD_PROMPT, user={"message": original}, task="office_chat_reword", ref=chat_id)
        text = redact(str(out.get("assistant_message", "")).strip()) if isinstance(out, dict) else ""
    except Exception as exc:  # noqa: BLE001 - any model failure keeps the deterministic wording
        logger.warning("Rewording failed, keeping the original: %s", exc)
        return original
    if not 15 <= len(text) <= 600 or re.search(r"https?://|wa\.me|www\.", text, re.IGNORECASE):
        return original
    if set(re.findall(r"\d+", text)) - set(re.findall(r"\d+", original)):
        return original
    return text


def decide_chat_turn(
    chat_session: OfficeChatSession,
    preferences: Optional[UserAppointmentPreferences],
    office: Optional[OfficeContact],
    scheme: SchemeContext,
    history: List[OfficeChatMessage],
    representative_message: str,
    llm: Optional[Any] = None,
    rep_result: Optional[Dict[str, Any]] = None,
) -> AssistantChatTurnDecision:
    """
    The Action Agent's next turn. Python decides what happens (status, slot, contact, whether the applicant must
    approve); a model, when one is passed in, may only reword the message. agent4 stays independent of member2: the
    caller supplies the model client.
    """
    decision = _decide_turn_heuristic(
        chat_session=chat_session,
        preferences=preferences,
        office=office,
        scheme=scheme,
        history=history,
        representative_message=representative_message,
        rep_result=rep_result,
    )
    if llm is not None:
        decision.assistant_message = _reworded(llm, decision.assistant_message, chat_session.chat_id)
    return decision
