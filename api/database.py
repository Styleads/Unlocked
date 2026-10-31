"""
api/database.py — Async SQLite session store for Project Unlocked.

Provides persistent, durable storage for citizen context, discovered schemes,
answers, history, assessments, document plans, and user progress across the
entire 6-stage lifecycle using aiosqlite in WAL mode.
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Union

import aiosqlite

from member2.models import (
    ActionPlan,
    Answer,
    AnswerState,
    Assessment,
    DocStatus,
    Question,
    SchemeRecord,
)
from member2.questions import apply_answers
from agent4.models import ApplicationProgress
from api.schemas import UserProfileInput

logger = logging.getLogger(__name__)

# Default database path: data/unlocked.db at repository root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_db_path(override: Optional[str] = None) -> str:
    """Resolve database path dynamically from parameter or environment."""
    if override:
        return override
    return os.getenv("DB_PATH", str(PROJECT_ROOT / "data" / "unlocked.db"))


DEFAULT_DB_PATH = get_db_path()

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL,
    preferred_language TEXT NOT NULL,
    state_status TEXT NOT NULL,
    context_json TEXT NOT NULL,
    raw_schemes_json TEXT,
    normalized_schemes_json TEXT,
    questions_json TEXT,
    answers_json TEXT,
    history_json TEXT,
    assessments_json TEXT,
    plan_json TEXT,
    user_documents_json TEXT,
    progress_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);

CREATE TABLE IF NOT EXISTS notification_preferences (
    session_id TEXT PRIMARY KEY,
    email TEXT,
    email_enabled INTEGER NOT NULL DEFAULT 0,
    categories_json TEXT NOT NULL DEFAULT '{}',
    consent_version TEXT NOT NULL DEFAULT 'v1',
    consent_at TIMESTAMP,
    disabled_at TIMESTAMP,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tracked_applications (
    application_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    scheme_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_started',
    status_source TEXT NOT NULL DEFAULT 'user_reported',
    reported_submission_at TIMESTAMP,
    recovery_status TEXT,
    recovery_data_json TEXT,
    last_updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tracked_apps_session ON tracked_applications(session_id);

CREATE TABLE IF NOT EXISTS appointments (
    appointment_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    application_id TEXT,
    related_task_id TEXT,
    purpose TEXT NOT NULL,
    scheduled_at_utc TIMESTAMP,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    location TEXT,
    status TEXT NOT NULL DEFAULT 'scheduled',
    outcome_summary TEXT,
    outcome_details_json TEXT,
    status_source TEXT NOT NULL DEFAULT 'user_reported',
    follow_up_at_utc TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_appointments_session ON appointments(session_id);

CREATE TABLE IF NOT EXISTS application_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    application_id TEXT,
    appointment_id TEXT,
    event_type TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT,
    source TEXT NOT NULL DEFAULT 'user_reported',
    details_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_app_events_session ON application_events(session_id);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    application_id TEXT,
    appointment_id TEXT,
    notification_type TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'email',
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_html TEXT,
    body_text TEXT,
    scheduled_at_utc TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'scheduled',
    provider TEXT NOT NULL DEFAULT 'resend',
    provider_message_id TEXT,
    idempotency_key TEXT UNIQUE,
    sent_at_utc TIMESTAMP,
    delivered_at_utc TIMESTAMP,
    last_error TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notifications_due ON notifications(status, scheduled_at_utc);
CREATE INDEX IF NOT EXISTS idx_notifications_session ON notifications(session_id);

CREATE TABLE IF NOT EXISTS follow_up_tokens (
    token_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    appointment_id TEXT,
    application_id TEXT,
    token_hash TEXT UNIQUE NOT NULL,
    expires_at_utc TIMESTAMP NOT NULL,
    revoked_at_utc TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_follow_up_hash ON follow_up_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_follow_up_session ON follow_up_tokens(session_id);
"""


# ---------------------------------------------------------------------------
# Serialization Utilities
# ---------------------------------------------------------------------------

def _to_json(obj: Any) -> str:
    """Safely serialize models, enums, and dicts to a JSON string."""
    if obj is None:
        return json.dumps(None)

    def _default(o: Any) -> Any:
        if hasattr(o, "model_dump"):
            return o.model_dump(mode="json")
        if isinstance(o, datetime):
            return o.isoformat()
        if hasattr(o, "value"):
            return o.value
        if isinstance(o, set):
            return list(o)
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    return json.dumps(obj, default=_default, ensure_ascii=False)


def _from_json(json_str: Optional[str], default: Any = None) -> Any:
    """Safely parse a JSON string, falling back to default on null/empty."""
    if not json_str:
        return default
    try:
        return json.loads(json_str)
    except Exception as exc:
        logger.warning("Failed to deserialize JSON data: %s", exc)
        return default


# ---------------------------------------------------------------------------
# Strongly Typed Session Object
# ---------------------------------------------------------------------------

@dataclass
class SessionRecord:
    session_id: str
    scope: str
    preferred_language: str
    state_status: str
    context: dict[str, Any]
    raw_schemes: list[dict[str, Any]] = field(default_factory=list)
    normalized_schemes: list[SchemeRecord] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    answers: dict[str, Answer] = field(default_factory=dict)
    history: dict[str, AnswerState] = field(default_factory=dict)
    assessments: list[Assessment] = field(default_factory=list)
    plan: Optional[ActionPlan] = None
    user_documents: dict[str, str] = field(default_factory=dict)
    progress: dict[str, ApplicationProgress] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def to_state_dict(self) -> dict[str, Any]:
        """Convert session record to complete dictionary for API response."""
        return {
            "session_id": self.session_id,
            "scope": self.scope,
            "preferred_language": self.preferred_language,
            "state_status": self.state_status,
            "context": self.context,
            "raw_schemes": self.raw_schemes,
            "normalized_schemes": [s.model_dump(mode="json") for s in self.normalized_schemes],
            "questions": [q.model_dump(mode="json") for q in self.questions],
            "answers": {k: v.model_dump(mode="json") for k, v in self.answers.items()},
            "history": {k: v.value for k, v in self.history.items()},
            "assessments": [a.model_dump(mode="json") for a in self.assessments],
            "plan": self.plan.model_dump(mode="json") if self.plan else None,
            "user_documents": self.user_documents,
            "progress": {k: v.model_dump(mode="json") for k, v in self.progress.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Database Initialization & Connection
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_connection(db_path: Optional[str] = None):
    """Connect to SQLite and configure high-concurrency WAL mode."""
    target_path = Path(get_db_path(db_path))
    target_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(target_path), timeout=30.0) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode = WAL;")
        await conn.execute("PRAGMA busy_timeout = 30000;")
        await conn.execute("PRAGMA synchronous = NORMAL;")
        yield conn


async def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and indexes."""
    async with get_connection(db_path) as conn:
        await conn.executescript(CREATE_TABLES_SQL)
        try:
            await conn.execute("ALTER TABLE sessions ADD COLUMN progress_json TEXT;")
        except Exception:
            pass  # Column already exists
        await conn.commit()
    logger.info("Database initialized at %s", db_path)


# ---------------------------------------------------------------------------
# Session CRUD Operations
# ---------------------------------------------------------------------------

async def create_session(
    session_id: str,
    context: Union[dict[str, Any], UserProfileInput],
    scope: str = "guided",
    preferred_language: str = "en",
    db_path: Optional[str] = None,
) -> SessionRecord:
    """
    Create a new session record in SQLite and seed initial answers and
    question history from provided context so already-known attributes
    are not re-asked.
    """
    # 1. Normalize context and extract seedable attributes
    if isinstance(context, UserProfileInput):
        context_dict = context.to_user_context()
        seed_list = context.extract_seedable_attributes()
    elif isinstance(context, dict):
        try:
            profile = UserProfileInput.model_validate(context)
            context_dict = profile.to_user_context()
            seed_list = profile.extract_seedable_attributes()
        except Exception:
            context_dict = context
            seed_list = []
    else:
        context_dict = {}
        seed_list = []

    # 2. Seed answers and history using member2.apply_answers
    initial_answers, initial_history = apply_answers({}, {}, seed_list)

    now_iso = datetime.now(timezone.utc).isoformat()
    state_status = "CONTEXT_INITIALIZED"

    sql = """
    INSERT INTO sessions (
        session_id, scope, preferred_language, state_status, context_json,
        raw_schemes_json, normalized_schemes_json, questions_json, answers_json,
        history_json, assessments_json, plan_json, user_documents_json,
        progress_json, created_at, updated_at
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
    );
    """

    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                session_id,
                scope,
                preferred_language,
                state_status,
                _to_json(context_dict),
                _to_json([]),
                _to_json([]),
                _to_json([]),
                _to_json(initial_answers),
                _to_json(initial_history),
                _to_json([]),
                _to_json(None),
                _to_json({}),
                _to_json({}),
                now_iso,
                now_iso,
            ),
        )
        await conn.commit()

    return SessionRecord(
        session_id=session_id,
        scope=scope,
        preferred_language=preferred_language,
        state_status=state_status,
        context=context_dict,
        raw_schemes=[],
        normalized_schemes=[],
        questions=[],
        answers=initial_answers,
        history=initial_history,
        assessments=[],
        plan=None,
        user_documents={},
        progress={},
        created_at=now_iso,
        updated_at=now_iso,
    )


async def get_session(session_id: str, db_path: Optional[str] = None) -> Optional[SessionRecord]:
    """Retrieve complete session record and deserialize into typed models."""
    sql = "SELECT * FROM sessions WHERE session_id = ?;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (session_id,)) as cursor:
            row = await cursor.fetchone()

    if not row:
        return None

    # Parse raw JSON structures
    context = _from_json(row["context_json"], {})
    raw_schemes = _from_json(row["raw_schemes_json"], [])
    normalized_schemes_data = _from_json(row["normalized_schemes_json"], [])
    questions_data = _from_json(row["questions_json"], [])
    answers_data = _from_json(row["answers_json"], {})
    history_data = _from_json(row["history_json"], {})
    assessments_data = _from_json(row["assessments_json"], [])
    plan_data = _from_json(row["plan_json"], None)
    user_documents = _from_json(row["user_documents_json"], {})
    progress_raw = row["progress_json"] if "progress_json" in row.keys() else None
    progress_data = _from_json(progress_raw, {})

    # Reconstruct typed Member 2 models
    normalized_schemes = [
        SchemeRecord.model_validate(s) for s in normalized_schemes_data
    ]
    questions = [
        Question.model_validate(q) for q in questions_data
    ]
    answers = {
        k: Answer.model_validate(v) for k, v in answers_data.items()
    }
    history = {
        k: AnswerState(v) for k, v in history_data.items()
    }
    assessments = [
        Assessment.model_validate(a) for a in assessments_data
    ]
    plan = ActionPlan.model_validate(plan_data) if plan_data else None
    progress = {
        k: ApplicationProgress.model_validate(v) for k, v in progress_data.items()
    } if progress_data else {}

    return SessionRecord(
        session_id=row["session_id"],
        scope=row["scope"],
        preferred_language=row["preferred_language"],
        state_status=row["state_status"],
        context=context,
        raw_schemes=raw_schemes,
        normalized_schemes=normalized_schemes,
        questions=questions,
        answers=answers,
        history=history,
        assessments=assessments,
        plan=plan,
        user_documents=user_documents,
        progress=progress,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def update_discovery_results(
    session_id: str,
    raw_schemes: list[Any],
    normalized_schemes: list[SchemeRecord],
    questions: list[Question],
    assessments: list[Assessment],
    state_status: str = "DISCOVERY_COMPLETE",
    db_path: Optional[str] = None,
) -> None:
    """Persist discovered schemes, normalized records, questions and initial assessments."""
    now_iso = datetime.now(timezone.utc).isoformat()
    sql = """
    UPDATE sessions SET
        raw_schemes_json = ?,
        normalized_schemes_json = ?,
        questions_json = ?,
        assessments_json = ?,
        state_status = ?,
        updated_at = ?
    WHERE session_id = ?;
    """
    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                _to_json(raw_schemes),
                _to_json(normalized_schemes),
                _to_json(questions),
                _to_json(assessments),
                state_status,
                now_iso,
                session_id,
            ),
        )
        await conn.commit()


async def update_answers_and_assessments(
    session_id: str,
    answers: Mapping[str, Answer],
    history: Mapping[str, AnswerState],
    assessments: list[Assessment],
    questions: Optional[list[Question]] = None,
    state_status: str = "ASSESSMENT_UPDATED",
    db_path: Optional[str] = None,
) -> None:
    """Persist updated answers, question history, and updated assessments."""
    now_iso = datetime.now(timezone.utc).isoformat()
    if questions is not None:
        sql = """
        UPDATE sessions SET
            answers_json = ?,
            history_json = ?,
            assessments_json = ?,
            questions_json = ?,
            state_status = ?,
            updated_at = ?
        WHERE session_id = ?;
        """
        params = (
            _to_json(dict(answers)),
            _to_json(dict(history)),
            _to_json(assessments),
            _to_json(questions),
            state_status,
            now_iso,
            session_id,
        )
    else:
        sql = """
        UPDATE sessions SET
            answers_json = ?,
            history_json = ?,
            assessments_json = ?,
            state_status = ?,
            updated_at = ?
        WHERE session_id = ?;
        """
        params = (
            _to_json(dict(answers)),
            _to_json(dict(history)),
            _to_json(assessments),
            state_status,
            now_iso,
            session_id,
        )

    async with get_connection(db_path) as conn:
        await conn.execute(sql, params)
        await conn.commit()


async def update_plan(
    session_id: str,
    plan: ActionPlan,
    user_documents: Optional[Mapping[str, Union[DocStatus, str]]] = None,
    state_status: str = "PLAN_GENERATED",
    db_path: Optional[str] = None,
) -> None:
    """Persist generated ActionPlan DAG and user document procurement statuses."""
    now_iso = datetime.now(timezone.utc).isoformat()
    sql = """
    UPDATE sessions SET
        plan_json = ?,
        user_documents_json = COALESCE(?, user_documents_json),
        state_status = ?,
        updated_at = ?
    WHERE session_id = ?;
    """
    doc_json = _to_json(dict(user_documents)) if user_documents is not None else None
    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                _to_json(plan),
                doc_json,
                state_status,
                now_iso,
                session_id,
            ),
        )
        await conn.commit()


async def update_user_documents(
    session_id: str,
    user_documents: Mapping[str, Union[DocStatus, str]],
    db_path: Optional[str] = None,
) -> None:
    """Update only user document statuses."""
    now_iso = datetime.now(timezone.utc).isoformat()
    sql = "UPDATE sessions SET user_documents_json = ?, updated_at = ? WHERE session_id = ?;"
    async with get_connection(db_path) as conn:
        await conn.execute(sql, (_to_json(dict(user_documents)), now_iso, session_id))
        await conn.commit()


async def delete_session(session_id: str, db_path: Optional[str] = None) -> bool:
    """Delete a session and all its stored citizen context from SQLite, cascading across all tables."""
    async with get_connection(db_path) as conn:
        await conn.execute("DELETE FROM follow_up_tokens WHERE session_id = ?;", (session_id,))
        await conn.execute("DELETE FROM notifications WHERE session_id = ?;", (session_id,))
        await conn.execute("DELETE FROM application_events WHERE session_id = ?;", (session_id,))
        await conn.execute("DELETE FROM appointments WHERE session_id = ?;", (session_id,))
        await conn.execute("DELETE FROM tracked_applications WHERE session_id = ?;", (session_id,))
        await conn.execute("DELETE FROM notification_preferences WHERE session_id = ?;", (session_id,))
        cursor = await conn.execute("DELETE FROM sessions WHERE session_id = ?;", (session_id,))
        await conn.commit()
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Notification Preferences CRUD
# ---------------------------------------------------------------------------

async def save_notification_preferences(
    session_id: str,
    email: Optional[str],
    email_enabled: bool,
    categories: Optional[dict[str, bool]] = None,
    consent_version: str = "v1",
    timezone_str: str = "Asia/Kolkata",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    cat_json = _to_json(categories or {})

    sql = """
    INSERT INTO notification_preferences (
        session_id, email, email_enabled, categories_json, consent_version,
        consent_at, disabled_at, timezone, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
    ON CONFLICT(session_id) DO UPDATE SET
        email = excluded.email,
        email_enabled = excluded.email_enabled,
        categories_json = excluded.categories_json,
        consent_version = excluded.consent_version,
        consent_at = CASE WHEN excluded.email_enabled = 1 THEN excluded.consent_at ELSE consent_at END,
        disabled_at = CASE WHEN excluded.email_enabled = 0 THEN excluded.updated_at ELSE NULL END,
        timezone = excluded.timezone,
        updated_at = excluded.updated_at;
    """
    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                session_id,
                email,
                1 if email_enabled else 0,
                cat_json,
                consent_version,
                now_iso if email_enabled else None,
                timezone_str,
                now_iso,
                now_iso,
            ),
        )
        await conn.commit()
    return await get_notification_preferences(session_id, db_path=db_path) or {}


async def get_notification_preferences(
    session_id: str,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    sql = "SELECT * FROM notification_preferences WHERE session_id = ?;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (session_id,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["email_enabled"] = bool(d["email_enabled"])
    d["categories"] = _from_json(d.get("categories_json"), {})
    return d


async def disable_notifications(
    session_id: str,
    db_path: Optional[str] = None,
) -> bool:
    """Disable notifications and cancel all pending/scheduled notifications for this session."""
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    async with get_connection(db_path) as conn:
        await conn.execute(
            """
            UPDATE notification_preferences
            SET email_enabled = 0, disabled_at = ?, updated_at = ?
            WHERE session_id = ?;
            """,
            (now_iso, now_iso, session_id),
        )
        await conn.execute(
            """
            UPDATE notifications
            SET status = 'cancelled', updated_at = ?
            WHERE session_id = ? AND status = 'scheduled';
            """,
            (now_iso, session_id),
        )
        await conn.commit()
    return True


# ---------------------------------------------------------------------------
# Tracked Applications CRUD
# ---------------------------------------------------------------------------

async def create_tracked_application(
    application_id: str,
    session_id: str,
    scheme_id: str,
    status: str = "not_started",
    status_source: str = "user_reported",
    reported_submission_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    sql = """
    INSERT INTO tracked_applications (
        application_id, session_id, scheme_id, status, status_source,
        reported_submission_at, recovery_status, recovery_data_json,
        last_updated_at, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?);
    """
    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                application_id,
                session_id,
                scheme_id,
                status,
                status_source,
                reported_submission_at,
                now_iso,
                now_iso,
            ),
        )
        await conn.commit()
    return await get_tracked_application(application_id, db_path=db_path) or {}


async def get_tracked_application(
    application_id: str,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    sql = "SELECT * FROM tracked_applications WHERE application_id = ?;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (application_id,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["recovery_data"] = _from_json(d.get("recovery_data_json"), None)
    return d


async def get_tracked_application_by_scheme(
    session_id: str,
    scheme_id: str,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    sql = "SELECT * FROM tracked_applications WHERE session_id = ? AND scheme_id = ? ORDER BY created_at DESC LIMIT 1;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (session_id, scheme_id)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["recovery_data"] = _from_json(d.get("recovery_data_json"), None)
    return d


async def list_tracked_applications(
    session_id: str,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM tracked_applications WHERE session_id = ? ORDER BY created_at ASC;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (session_id,)) as cursor:
            rows = await cursor.fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["recovery_data"] = _from_json(d.get("recovery_data_json"), None)
        res.append(d)
    return res


async def update_tracked_application(
    application_id: str,
    status: Optional[str] = None,
    status_source: Optional[str] = None,
    reported_submission_at: Optional[str] = None,
    recovery_status: Optional[str] = None,
    recovery_data: Optional[Any] = None,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    fields = ["last_updated_at = ?"]
    params: list[Any] = [now_iso]

    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if status_source is not None:
        fields.append("status_source = ?")
        params.append(status_source)
    if reported_submission_at is not None:
        fields.append("reported_submission_at = ?")
        params.append(reported_submission_at)
    if recovery_status is not None:
        fields.append("recovery_status = ?")
        params.append(recovery_status)
    if recovery_data is not None:
        fields.append("recovery_data_json = ?")
        params.append(_to_json(recovery_data))

    params.append(application_id)
    sql = f"UPDATE tracked_applications SET {', '.join(fields)} WHERE application_id = ?;"
    async with get_connection(db_path) as conn:
        await conn.execute(sql, params)
        await conn.commit()
    return await get_tracked_application(application_id, db_path=db_path)


# ---------------------------------------------------------------------------
# Appointments CRUD
# ---------------------------------------------------------------------------

async def create_appointment(
    appointment_id: str,
    session_id: str,
    purpose: str,
    scheduled_at_utc: Optional[str] = None,
    timezone_str: str = "Asia/Kolkata",
    location: Optional[str] = None,
    application_id: Optional[str] = None,
    related_task_id: Optional[str] = None,
    status: str = "scheduled",
    status_source: str = "user_reported",
    follow_up_at_utc: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    sql = """
    INSERT INTO appointments (
        appointment_id, session_id, application_id, related_task_id,
        purpose, scheduled_at_utc, timezone, location, status,
        outcome_summary, outcome_details_json, status_source,
        follow_up_at_utc, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?);
    """
    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                appointment_id,
                session_id,
                application_id,
                related_task_id,
                purpose,
                scheduled_at_utc,
                timezone_str,
                location,
                status,
                status_source,
                follow_up_at_utc,
                now_iso,
                now_iso,
            ),
        )
        await conn.commit()
    return await get_appointment(appointment_id, db_path=db_path) or {}


async def get_appointment(
    appointment_id: str,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    sql = "SELECT * FROM appointments WHERE appointment_id = ?;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (appointment_id,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["outcome_details"] = _from_json(d.get("outcome_details_json"), None)
    return d


async def list_appointments(
    session_id: str,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM appointments WHERE session_id = ? ORDER BY scheduled_at_utc ASC;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (session_id,)) as cursor:
            rows = await cursor.fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["outcome_details"] = _from_json(d.get("outcome_details_json"), None)
        res.append(d)
    return res


async def update_appointment(
    appointment_id: str,
    status: Optional[str] = None,
    scheduled_at_utc: Optional[str] = None,
    location: Optional[str] = None,
    outcome_summary: Optional[str] = None,
    outcome_details: Optional[Any] = None,
    status_source: Optional[str] = None,
    follow_up_at_utc: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    fields = ["updated_at = ?"]
    params: list[Any] = [now_iso]

    if status is not None:
        fields.append("status = ?")
        params.append(status)
    if scheduled_at_utc is not None:
        fields.append("scheduled_at_utc = ?")
        params.append(scheduled_at_utc)
    if location is not None:
        fields.append("location = ?")
        params.append(location)
    if outcome_summary is not None:
        fields.append("outcome_summary = ?")
        params.append(outcome_summary)
    if outcome_details is not None:
        fields.append("outcome_details_json = ?")
        params.append(_to_json(outcome_details))
    if status_source is not None:
        fields.append("status_source = ?")
        params.append(status_source)
    if follow_up_at_utc is not None:
        fields.append("follow_up_at_utc = ?")
        params.append(follow_up_at_utc)

    params.append(appointment_id)
    sql = f"UPDATE appointments SET {', '.join(fields)} WHERE appointment_id = ?;"
    async with get_connection(db_path) as conn:
        await conn.execute(sql, params)
        await conn.commit()
    return await get_appointment(appointment_id, db_path=db_path)


# ---------------------------------------------------------------------------
# Application Events CRUD
# ---------------------------------------------------------------------------

async def record_application_event(
    event_id: str,
    session_id: str,
    event_type: str,
    application_id: Optional[str] = None,
    appointment_id: Optional[str] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    source: str = "user_reported",
    details: Optional[Any] = None,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    sql = """
    INSERT INTO application_events (
        event_id, session_id, application_id, appointment_id,
        event_type, old_status, new_status, source, details_json, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                event_id,
                session_id,
                application_id,
                appointment_id,
                event_type,
                old_status,
                new_status,
                source,
                _to_json(details),
                now_iso,
            ),
        )
        await conn.commit()
    return {
        "event_id": event_id,
        "session_id": session_id,
        "application_id": application_id,
        "appointment_id": appointment_id,
        "event_type": event_type,
        "old_status": old_status,
        "new_status": new_status,
        "source": source,
        "details": details,
        "created_at": now_iso,
    }


async def list_application_events(
    session_id: str,
    application_id: Optional[str] = None,
    appointment_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    params: list[Any] = [session_id]
    clauses = ["session_id = ?"]
    if application_id:
        clauses.append("application_id = ?")
        params.append(application_id)
    if appointment_id:
        clauses.append("appointment_id = ?")
        params.append(appointment_id)

    sql = f"SELECT * FROM application_events WHERE {' AND '.join(clauses)} ORDER BY created_at ASC;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["details"] = _from_json(d.get("details_json"), None)
        res.append(d)
    return res


# ---------------------------------------------------------------------------
# Notifications CRUD
# ---------------------------------------------------------------------------

async def create_notification(
    notification_id: str,
    session_id: str,
    notification_type: str,
    recipient: str,
    subject: str,
    body_html: Optional[str] = None,
    body_text: Optional[str] = None,
    scheduled_at_utc: Optional[str] = None,
    application_id: Optional[str] = None,
    appointment_id: Optional[str] = None,
    channel: str = "email",
    provider: str = "resend",
    idempotency_key: Optional[str] = None,
    is_demo: bool = False,
    status: str = "scheduled",
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    sql = """
    INSERT INTO notifications (
        notification_id, session_id, application_id, appointment_id,
        notification_type, channel, recipient, subject, body_html, body_text,
        scheduled_at_utc, status, provider, provider_message_id,
        idempotency_key, sent_at_utc, delivered_at_utc, last_error,
        is_demo, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, ?, ?, ?);
    """
    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                notification_id,
                session_id,
                application_id,
                appointment_id,
                notification_type,
                channel,
                recipient,
                subject,
                body_html,
                body_text,
                scheduled_at_utc,
                status,
                provider,
                idempotency_key,
                1 if is_demo else 0,
                now_iso,
                now_iso,
            ),
        )
        await conn.commit()
    return await get_notification(notification_id, db_path=db_path) or {}


async def get_notification(
    notification_id: str,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    sql = "SELECT * FROM notifications WHERE notification_id = ?;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (notification_id,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    d = dict(row)
    d["is_demo"] = bool(d.get("is_demo", 0))
    return d


async def list_notifications(
    session_id: str,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM notifications WHERE session_id = ? ORDER BY created_at DESC;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (session_id,)) as cursor:
            rows = await cursor.fetchall()
    res = []
    for r in rows:
        d = dict(r)
        d["is_demo"] = bool(d.get("is_demo", 0))
        res.append(d)
    return res


async def cancel_notification(
    notification_id: str,
    db_path: Optional[str] = None,
) -> bool:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    sql = "UPDATE notifications SET status = 'cancelled', updated_at = ? WHERE notification_id = ? AND status = 'scheduled';"
    async with get_connection(db_path) as conn:
        cursor = await conn.execute(sql, (now_iso, notification_id))
        await conn.commit()
        return cursor.rowcount > 0


async def cancel_pending_notifications_for_appointment(
    appointment_id: str,
    notification_types: Optional[list[str]] = None,
    db_path: Optional[str] = None,
) -> int:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    clauses = ["appointment_id = ?", "status = 'scheduled'"]
    params: list[Any] = [now_iso, appointment_id]
    if notification_types:
        placeholders = ", ".join(["?"] * len(notification_types))
        clauses.append(f"notification_type IN ({placeholders})")
        params.extend(notification_types)

    sql = f"UPDATE notifications SET status = 'cancelled', updated_at = ? WHERE {' AND '.join(clauses)};"
    async with get_connection(db_path) as conn:
        cursor = await conn.execute(sql, params)
        await conn.commit()
        return cursor.rowcount


async def claim_due_notifications(
    now_iso: str,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Atomically find and claim notifications scheduled on or before now_iso.
    Transitions status from 'scheduled' to 'processing' in a single transaction.
    """
    async with get_connection(db_path) as conn:
        # Find due notifications
        find_sql = """
        SELECT notification_id FROM notifications
        WHERE status = 'scheduled' AND (scheduled_at_utc IS NULL OR scheduled_at_utc <= ?)
        ORDER BY scheduled_at_utc ASC
        LIMIT ?;
        """
        async with conn.execute(find_sql, (now_iso, limit)) as cursor:
            rows = await cursor.fetchall()
            ids = [row["notification_id"] for row in rows]

        if not ids:
            return []

        # Claim them
        placeholders = ", ".join(["?"] * len(ids))
        claim_sql = f"""
        UPDATE notifications
        SET status = 'processing', updated_at = ?
        WHERE notification_id IN ({placeholders}) AND status = 'scheduled';
        """
        await conn.execute(claim_sql, [now_iso] + ids)
        await conn.commit()

        # Fetch claimed details
        fetch_sql = f"SELECT * FROM notifications WHERE notification_id IN ({placeholders});"
        async with conn.execute(fetch_sql, ids) as cursor:
            claimed_rows = await cursor.fetchall()

    res = []
    for r in claimed_rows:
        d = dict(r)
        d["is_demo"] = bool(d.get("is_demo", 0))
        res.append(d)
    return res


async def update_notification_status(
    notification_id: str,
    status: str,
    provider_message_id: Optional[str] = None,
    sent_at_utc: Optional[str] = None,
    delivered_at_utc: Optional[str] = None,
    last_error: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    fields = ["status = ?", "updated_at = ?"]
    params: list[Any] = [status, now_iso]

    if provider_message_id is not None:
        fields.append("provider_message_id = ?")
        params.append(provider_message_id)
    if sent_at_utc is not None:
        fields.append("sent_at_utc = ?")
        params.append(sent_at_utc)
    if delivered_at_utc is not None:
        fields.append("delivered_at_utc = ?")
        params.append(delivered_at_utc)
    if last_error is not None:
        fields.append("last_error = ?")
        params.append(last_error)

    params.append(notification_id)
    sql = f"UPDATE notifications SET {', '.join(fields)} WHERE notification_id = ?;"
    async with get_connection(db_path) as conn:
        await conn.execute(sql, params)
        await conn.commit()
    return await get_notification(notification_id, db_path=db_path)


# ---------------------------------------------------------------------------
# Follow-up Tokens CRUD
# ---------------------------------------------------------------------------

async def create_follow_up_token(
    token_id: str,
    session_id: str,
    token_hash: str,
    expires_at_utc: str,
    appointment_id: Optional[str] = None,
    application_id: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict[str, Any]:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    sql = """
    INSERT INTO follow_up_tokens (
        token_id, session_id, appointment_id, application_id,
        token_hash, expires_at_utc, revoked_at_utc, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?);
    """
    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                token_id,
                session_id,
                appointment_id,
                application_id,
                token_hash,
                expires_at_utc,
                now_iso,
            ),
        )
        await conn.commit()
    return {
        "token_id": token_id,
        "session_id": session_id,
        "appointment_id": appointment_id,
        "application_id": application_id,
        "token_hash": token_hash,
        "expires_at_utc": expires_at_utc,
        "revoked_at_utc": None,
        "created_at": now_iso,
    }


async def get_follow_up_token_by_hash(
    token_hash: str,
    db_path: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    sql = "SELECT * FROM follow_up_tokens WHERE token_hash = ?;"
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (token_hash,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        return None
    return dict(row)


async def revoke_follow_up_token(
    token_hash: str,
    db_path: Optional[str] = None,
) -> bool:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    sql = "UPDATE follow_up_tokens SET revoked_at_utc = ? WHERE token_hash = ? AND revoked_at_utc IS NULL;"
    async with get_connection(db_path) as conn:
        cursor = await conn.execute(sql, (now_iso, token_hash))
        await conn.commit()
        return cursor.rowcount > 0


async def revoke_session_tokens(
    session_id: str,
    db_path: Optional[str] = None,
) -> int:
    from api.clock import now_utc
    now_iso = now_utc().isoformat()
    sql = "UPDATE follow_up_tokens SET revoked_at_utc = ? WHERE session_id = ? AND revoked_at_utc IS NULL;"
    async with get_connection(db_path) as conn:
        cursor = await conn.execute(sql, (now_iso, session_id))
        await conn.commit()
        return cursor.rowcount



async def list_sessions(limit: int = 50, db_path: Optional[str] = None) -> list[dict[str, Any]]:
    """List recent sessions for operational monitoring."""
    sql = """
    SELECT session_id, scope, preferred_language, state_status, created_at, updated_at
    FROM sessions ORDER BY updated_at DESC LIMIT ?;
    """
    async with get_connection(db_path) as conn:
        async with conn.execute(sql, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_scheme_progress(
    session_id: str,
    scheme_id: str,
    scheme_progress: ApplicationProgress,
    db_path: Optional[str] = None,
) -> SessionRecord:
    """Update user-reported application progress for a specific scheme in SQLite."""
    session = await get_session(session_id, db_path=db_path)
    if not session:
        raise KeyError(f"Session '{session_id}' not found.")

    session.progress[scheme_id] = scheme_progress
    now_iso = datetime.now(timezone.utc).isoformat()
    sql = "UPDATE sessions SET progress_json = ?, updated_at = ? WHERE session_id = ?;"
    async with get_connection(db_path) as conn:
        await conn.execute(
            sql,
            (
                _to_json({k: v.model_dump(mode="json") for k, v in session.progress.items()}),
                now_iso,
                session_id,
            ),
        )
        await conn.commit()
    session.updated_at = now_iso
    return session

