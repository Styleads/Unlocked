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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);
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
    async with aiosqlite.connect(str(target_path)) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode = WAL;")
        await conn.execute("PRAGMA busy_timeout = 5000;")
        await conn.execute("PRAGMA synchronous = NORMAL;")
        yield conn


async def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and indexes."""
    async with get_connection(db_path) as conn:
        await conn.executescript(CREATE_TABLES_SQL)
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
        created_at, updated_at
    ) VALUES (
        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
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
    """Delete a session and all its stored citizen context from SQLite."""
    sql = "DELETE FROM sessions WHERE session_id = ?;"
    async with get_connection(db_path) as conn:
        cursor = await conn.execute(sql, (session_id,))
        await conn.commit()
        return cursor.rowcount > 0


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
