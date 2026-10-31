"""
api/clock.py — Clock abstraction for real-time and accelerated demo simulation.

Enforces:
- Production clock uses real UTC time.
- Demo mode clock allows accelerating or freezing time for demonstrations without
  ever modifying the machine or operating system clock.
- Demo clock actions are strictly disabled when DEMO_MODE is false.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

_demo_offset_seconds: float = 0.0
_demo_frozen_time: Optional[datetime] = None


def is_demo_mode() -> bool:
    """Check if demo mode is enabled via environment."""
    val = os.getenv("DEMO_MODE", "false").strip().lower()
    return val in ("true", "1", "yes", "on")


def now_utc() -> datetime:
    """
    Return the current UTC datetime.
    When DEMO_MODE is true, applies the simulated demo offset or frozen time.
    When DEMO_MODE is false, always returns real UTC time.
    """
    if not is_demo_mode():
        return datetime.now(timezone.utc)
    if _demo_frozen_time is not None:
        return _demo_frozen_time
    return datetime.now(timezone.utc) + timedelta(seconds=_demo_offset_seconds)


def advance_demo_time(seconds: float) -> datetime:
    """
    Advance simulated time by a number of seconds.
    Raises PermissionError if DEMO_MODE is not enabled.
    """
    if not is_demo_mode():
        raise PermissionError("Demo mode is disabled; cannot advance simulated clock.")
    global _demo_offset_seconds, _demo_frozen_time
    if _demo_frozen_time is not None:
        _demo_frozen_time += timedelta(seconds=seconds)
        return _demo_frozen_time
    _demo_offset_seconds += seconds
    return now_utc()


def set_demo_time(target_utc: datetime) -> datetime:
    """
    Explicitly set the simulated demo time to a target UTC datetime.
    Raises PermissionError if DEMO_MODE is not enabled.
    """
    if not is_demo_mode():
        raise PermissionError("Demo mode is disabled; cannot set simulated clock.")
    global _demo_frozen_time, _demo_offset_seconds
    if target_utc.tzinfo is None:
        target_utc = target_utc.replace(tzinfo=timezone.utc)
    else:
        target_utc = target_utc.astimezone(timezone.utc)
    _demo_frozen_time = target_utc
    return _demo_frozen_time


def reset_demo_time() -> None:
    """Reset simulated clock offsets back to real time."""
    global _demo_offset_seconds, _demo_frozen_time
    _demo_offset_seconds = 0.0
    _demo_frozen_time = None

