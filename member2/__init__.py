"""Unlocked, Member 2: Eligibility & Verification + Document & Planning.

All functions are synchronous and side-effect free (no DB; no network except the
optional LLM adapter). Member 3 owns persistence and passes answers and question
history in and out. See README.md.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from .agent3 import Agent3
from .assess import AnswersInput, SchemeInput, assess_requirement, assess_scheme, assess_schemes, reassess_schemes
from .attributes import ATTRIBUTES, resolve_attribute
from .data_loader import (
    list_available_categories,
    load_all_schemes,
    load_document_definitions,
    load_schemes_by_category,
    load_schemes_from_file,
)
from .documents import DOCUMENTS, get_issuing_authority, load_document_registry, normalize_document_name, reload_document_registry
from .llm import AnthropicClient, GeminiClient, LLMClient, LLMError, default_client
from .models import (
    ActionPlan,
    Answer,
    AnswerState,
    Assessment,
    ChecklistItem,
    DocStatus,
    DocumentDependency,
    DocumentRequirement,
    GraphEdge,
    GraphNode,
    InputType,
    Operator,
    Question,
    RangeOption,
    RankedDocument,
    Requirement,
    RequirementCategory,
    RequirementResult,
    RequirementStatus,
    RequirementVerification,
    RuleCondition,
    SchemeRecord,
    SchemeStatus,
    Sensitivity,
    VerificationStatus,
)
from .normalize import normalize_requirements, normalize_scheme, requirement_matrix
from .planning import build_action_plan, render_mermaid, render_obsidian_notes
from .questions import HistoryInput, apply_answers, generate_consolidated_questions, generate_scheme_questions


def run_pipeline(
    schemes: Iterable[SchemeInput],
    user_answers: AnswersInput = None,
    question_history: HistoryInput = None,
    *,
    llm: Optional[LLMClient] = None,
    batch_size: int = 5,
) -> dict[str, Any]:
    """Normalize, assess and generate the next question batch, as JSON-ready dicts.

    Persist the returned "schemes": they carry the markers that stop the LLM from
    being called again for the same scheme on the next run.
    """
    normalized = normalize_requirements(schemes, llm)
    assessments = assess_schemes(normalized, user_answers)
    questions = generate_consolidated_questions(normalized, user_answers, question_history, batch_size=batch_size)
    return {
        "schemes": [s.model_dump(mode="json") for s in normalized],
        "assessments": [a.model_dump(mode="json") for a in assessments],
        "questions": [q.model_dump(mode="json") for q in questions],
    }


__all__ = [
    # workflow & planning
    "normalize_scheme", "normalize_requirements", "requirement_matrix",
    "assess_requirement", "assess_scheme", "assess_schemes", "reassess_schemes",
    "generate_consolidated_questions", "generate_scheme_questions", "apply_answers",
    "build_action_plan", "render_mermaid", "render_obsidian_notes", "run_pipeline",
    "Agent3",
    # data loaders
    "load_schemes_from_file", "load_schemes_by_category", "load_all_schemes",
    "list_available_categories", "load_document_definitions",
    # LLM
    "LLMClient", "AnthropicClient", "GeminiClient", "default_client", "LLMError",
    # registries
    "ATTRIBUTES", "DOCUMENTS", "resolve_attribute", "normalize_document_name",
    "load_document_registry", "reload_document_registry", "get_issuing_authority",
    # models
    "ActionPlan", "Answer", "AnswerState", "Assessment", "ChecklistItem", "DocStatus",
    "DocumentDependency", "DocumentRequirement", "GraphEdge", "GraphNode", "InputType",
    "Operator", "Question", "RangeOption", "RankedDocument", "Requirement", "RequirementCategory", "RequirementResult", "RuleCondition",
    "RequirementStatus", "RequirementVerification", "SchemeRecord", "SchemeStatus",
    "Sensitivity", "VerificationStatus",
]
