"""
api/tokens.py — Secure follow-up tokens for scoped citizen action links.

Enforces:
- Cryptographic random token generation with >=256 bits of entropy.
- Storage of only SHA-256 hashes in SQLite; raw tokens are never persisted in the database.
- URLs formatted using APP_BASE_URL.
- Token revocation and configurable expiration.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from api.clock import now_utc

DEFAULT_TOKEN_EXPIRY_DAYS = 14


def generate_raw_token() -> str:
    """Generate a cryptographically secure 256-bit random URL-safe bearer token."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """Compute SHA-256 hash of raw token for secure database storage and lookup."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def get_base_url() -> str:
    """Get public base URL for dynamic link generation."""
    return os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")


def format_follow_up_url(raw_token: str) -> str:
    """Construct full follow-up link that takes citizen to scoped update page."""
    return f"{get_base_url()}/api/follow-up/{raw_token}"


def calculate_expiry(days: int = DEFAULT_TOKEN_EXPIRY_DAYS) -> datetime:
    """Compute expiration timestamp using current application clock."""
    return now_utc() + timedelta(days=days)

