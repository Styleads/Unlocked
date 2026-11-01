"""
api/office_simulator.py — Controlled Python Scenario Engine for Simulated Office Representative.

Enforces:
1. Purely deterministic dialogue responses driven by fixtures (fixtures/office_chat_scenarios.json).
2. Zero reliance on uncontrolled LLMs for office policies, slots, or confirmations.
3. Accurate matching against user availability windows and published office hours.
4. Support for the 4 core demo scenarios:
   - Scenario A: Successful Appointment Offer & Confirmation
   - Scenario B: No Availability
   - Scenario C: Missing Information Request & Receiver WhatsApp Handoff
   - Scenario D: Unsupported Channel / Ambiguous Response
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agent4.office_chat_models import OfficeContact, UserAppointmentPreferences

logger = logging.getLogger(__name__)

FIXTURES_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "office_chat_scenarios.json"


class SimulatorTurnResult(BaseModel):
    """Structured response from the simulated office representative."""
    message: str
    sender: str = "simulated_office"
    turn_index: int
    scenario_id: str
    intent: str
    offered_slot: Optional[Dict[str, Any]] = None
    confirmed_slot: Optional[Dict[str, Any]] = None
    receiver_whatsapp_number: Optional[str] = None
    requested_info: Optional[str] = None
    is_terminal: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


def parse_time_str(time_str: str) -> Optional[time]:
    """Parse time string like '11:00', '11:00 AM', '14:30' into datetime.time."""
    if not time_str:
        return None
    cleaned = time_str.strip().upper()
    try:
        # Check AM/PM
        if "AM" in cleaned or "PM" in cleaned:
            dt = datetime.strptime(cleaned, "%I:%M %p")
            return dt.time()
        # Check 24-hr HH:MM
        parts = cleaned.split(":")
        if len(parts) >= 2:
            return time(int(parts[0]), int(parts[1]))
    except Exception:
        pass
    return None


def is_time_within_range(t: time, start_t: time, end_t: time) -> bool:
    """Return True if time t is within [start_t, end_t]."""
    return start_t <= t <= end_t


class OfficeSimulatorService:
    """Service that acts as the simulated welfare office representative."""

    def __init__(self, fixtures_file: Optional[Path] = None) -> None:
        self.fixtures_file = fixtures_file or FIXTURES_PATH
        self._scenarios: Dict[str, Any] = {}
        self._load_fixtures()

    def _load_fixtures(self) -> None:
        if not self.fixtures_file.exists():
            logger.warning("Scenarios file not found at %s", self.fixtures_file)
            self._scenarios = {}
            return
        try:
            with open(self.fixtures_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._scenarios = data.get("scenarios", {})
        except Exception as exc:
            logger.error("Failed to load scenario fixtures: %s", exc)
            self._scenarios = {}

    def get_available_scenarios(self) -> List[Dict[str, Any]]:
        """List all available scenario IDs, titles, and types for demo selection."""
        results = []
        for s_id, s_data in self._scenarios.items():
            results.append({
                "scenario_id": s_id,
                "scenario_type": s_data.get("scenario_type", "custom"),
                "title": s_data.get("title", s_id),
                "description": s_data.get("description", ""),
            })
        return results

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """Get full configuration for a scenario."""
        return self._scenarios.get(scenario_id)

    def is_slot_within_office_hours(
        self,
        day: str,
        time_val: time,
        office_hours: Optional[Dict[str, Any]],
    ) -> bool:
        """Check whether proposed day and time fall within published office hours."""
        if not office_hours or not isinstance(office_hours, dict):
            # If no published hours exist, fallback window is 10:00 - 17:30 Mon-Fri
            return day.lower() in ["monday", "tuesday", "wednesday", "thursday", "friday"] and (
                time(10, 0) <= time_val <= time(17, 30)
            )

        day_key = day.lower()
        if day_key not in office_hours:
            return False

        day_schedule = office_hours.get(day_key)
        if not isinstance(day_schedule, dict):
            return False

        open_str = day_schedule.get("open", "10:00")
        close_str = day_schedule.get("close", "17:30")
        open_time = parse_time_str(open_str) or time(10, 0)
        close_time = parse_time_str(close_str) or time(17, 30)

        return is_time_within_range(time_val, open_time, close_time)

    def is_slot_within_user_preferences(
        self,
        day: str,
        time_val: time,
        preferences: Optional[UserAppointmentPreferences],
    ) -> bool:
        """Check whether proposed day and time match citizen's preferred windows."""
        if not preferences:
            return True

        # Check day
        pref_days = [d.lower() for d in preferences.preferred_days]
        if pref_days and day.lower() not in pref_days:
            return False

        # Check windows
        if not preferences.preferred_windows:
            return True

        for window in preferences.preferred_windows:
            w_start = parse_time_str(window.start)
            w_end = parse_time_str(window.end)
            if w_start and w_end and is_time_within_range(time_val, w_start, w_end):
                return True

        return False

    def process_turn(
        self,
        scenario_id: str,
        turn_index: int,
        assistant_message: str,
        preferences: Optional[UserAppointmentPreferences] = None,
        office: Optional[OfficeContact] = None,
    ) -> SimulatorTurnResult:
        """
        Advance representative dialogue deterministically based on scenario and turn index.
        Even turns (2, 4, ...) are spoken by the simulated representative.
        """
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            # Fallback to scenario_a_success if unknown
            scenario = self.get_scenario("scenario_a_success")
            if not scenario:
                return SimulatorTurnResult(
                    message="Namaskara! This is the simulated welfare office representative. How can we help?",
                    turn_index=turn_index,
                    scenario_id=scenario_id,
                    intent="default_greeting",
                )

        turns = scenario.get("turns", [])
        # Find matching turn in fixture
        matched_turn = next((t for t in turns if t.get("turn_index") == turn_index), None)

        if not matched_turn:
            # If past the last fixture turn, conclude politely
            return SimulatorTurnResult(
                message="The simulated enquiry for this office is concluded. Thank you for contacting Unlocked.",
                turn_index=turn_index,
                scenario_id=scenario_id,
                intent="terminal_closure",
                is_terminal=True,
            )

        msg_text = matched_turn.get("message", "")
        meta = matched_turn.get("metadata", {})
        intent = meta.get("intent", "reply")
        offered = meta.get("offered_slot")
        confirmed = meta.get("confirmed_slot")
        whatsapp_num = meta.get("receiver_whatsapp_number")
        req_info = meta.get("requested_info")

        # Validate offered slot against office hours and preferences if applicable
        if offered and preferences:
            offered_day = offered.get("day", "monday")
            offered_time = parse_time_str(offered.get("time", "11:00"))
            office_hours = office.office_hours if office else None
            in_office_hours = self.is_slot_within_office_hours(offered_day, offered_time, office_hours) if offered_time else True
            in_prefs = self.is_slot_within_user_preferences(offered_day, offered_time, preferences) if offered_time else True

            meta["within_office_hours"] = in_office_hours
            meta["within_user_preferences"] = in_prefs

        return SimulatorTurnResult(
            message=msg_text,
            turn_index=turn_index,
            scenario_id=scenario_id,
            intent=intent,
            offered_slot=offered,
            confirmed_slot=confirmed,
            receiver_whatsapp_number=whatsapp_num,
            requested_info=req_info,
            is_terminal=meta.get("is_terminal", False),
            metadata=meta,
        )
