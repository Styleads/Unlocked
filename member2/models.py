"""Shared data models. Field names follow plan.md §5; deviations are in DECISIONS.md."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VerificationStatus(str, Enum):
    """Scheme-level verification (plan §5.1: "not_verified")."""

    verified = "verified"
    not_verified = "not_verified"
    uncertain = "uncertain"


class RequirementVerification(str, Enum):
    """Requirement-level verification (plan §5.1: "unverified")."""

    verified = "verified"
    unverified = "unverified"
    uncertain = "uncertain"


class Operator(str, Enum):
    lte = "lte"
    lt = "lt"
    gte = "gte"
    gt = "gt"
    eq = "eq"
    neq = "neq"
    in_ = "in"
    not_in = "not_in"
    is_true = "is_true"
    is_false = "is_false"


class RuleCondition(BaseModel):
    """The group a requirement applies to, e.g. marks >= 60 only when
    social_category in [SC, ST]. Evaluated like a requirement."""

    attribute: str
    operator: Operator
    value: Any = None


class Requirement(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = ""  # filled by the normalizer if Member 1 omits it
    attribute: Optional[str] = None  # canonical id, "unmapped:<slug>", or None
    criterion: str  # original text, preserved verbatim
    operator: Optional[Operator] = None
    value: Any = None
    status: RequirementVerification = RequirementVerification.unverified
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    condition: Optional[RuleCondition] = None  # applies only to this group (DECISIONS #61)

    @field_validator("status", mode="before")
    @classmethod
    def _accept_scheme_vocabulary(cls, v: Any) -> Any:
        # Members 1/3 may reuse the scheme-level word; it means the same thing here.
        return RequirementVerification.unverified if v == "not_verified" else v


class DocumentDependency(BaseModel):
    depends_on: str  # raw document name; normalized in planning
    source_url: Optional[str] = None
    evidence: Optional[str] = None


class DocumentRequirement(BaseModel):
    name: str  # raw name as found
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    dependencies: list[DocumentDependency] = Field(default_factory=list)

    @field_validator("dependencies", mode="before")
    @classmethod
    def _coerce_string_dependencies(cls, v: Any) -> Any:
        if isinstance(v, list):
            return [{"depends_on": d} if isinstance(d, str) else d for d in v]
        return v


class SchemeRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    summary: Optional[str] = None
    government_level: Optional[str] = None
    department: Optional[str] = None
    target_group: list[str] = Field(default_factory=list)
    eligibility_text: Optional[str] = None  # raw text for the normalizer
    requirements: list[Requirement] = Field(default_factory=list)
    benefit: Any = None
    documents: list[DocumentRequirement] = Field(default_factory=list)
    application_steps: list[str] = Field(default_factory=list)
    application_url: Optional[str] = None
    deadline: Optional[str] = None  # ISO date, only if verified
    deadline_source_url: Optional[str] = None
    official_sources: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.not_verified
    uncertainties: list[str] = Field(default_factory=list)
    source_type: str = "live_search"  # "live_search" | "fallback"

    @field_validator("documents", mode="before")
    @classmethod
    def _coerce_string_documents(cls, v: Any) -> Any:
        # A bare name has no source, so planning will exclude it with a warning
        # instead of the whole record failing validation.
        if isinstance(v, list):
            return [{"name": d} if isinstance(d, str) else d for d in v]
        return v

    @field_validator("verification_status", mode="before")
    @classmethod
    def _accept_requirement_vocabulary(cls, v: Any) -> Any:
        return VerificationStatus.not_verified if v == "unverified" else v


class AnswerState(str, Enum):
    unanswered = "unanswered"
    answered = "answered"
    skipped = "skipped"
    unknown = "unknown"  # user said "not sure"
    prefer_not_to_answer = "prefer_not_to_answer"


class Answer(BaseModel):
    attribute: str
    state: AnswerState
    value: Any = None  # only kept when state == answered

    @model_validator(mode="after")
    def _drop_value_unless_answered(self) -> "Answer":
        # A skipped answer must not carry a value that could later be compared.
        if self.state != AnswerState.answered:
            self.value = None
        return self


class RequirementStatus(str, Enum):
    satisfied = "satisfied"
    not_satisfied = "not_satisfied"
    unknown = "unknown"
    needs_clarification = "needs_clarification"
    unverified = "unverified"


class RequirementResult(BaseModel):
    requirement_id: str
    attribute: Optional[str] = None
    status: RequirementStatus
    reason: str
    criterion: str
    source_url: Optional[str] = None


class SchemeStatus(str, Enum):
    potential_match = "potential_match"
    more_information_needed = "more_information_needed"
    not_yet_verified = "not_yet_verified"
    unlikely_to_match = "unlikely_to_match"
    uncertain = "uncertain"


class Assessment(BaseModel):
    scheme_id: str
    status: SchemeStatus
    explanation: str
    requirements: list[RequirementResult] = Field(default_factory=list)
    missing_attributes: list[str] = Field(default_factory=list)
    last_assessed_at: Optional[str] = None  # ISO timestamp (UTC)


class Sensitivity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class InputType(str, Enum):
    number = "number"
    range = "range"
    select = "select"
    boolean = "boolean"
    text = "text"


class RangeOption(BaseModel):
    """A UI band for a range attribute; maps to an answer of {"min", "max"}."""

    label: str
    min: Optional[float] = None
    max: Optional[float] = None  # inclusive; None = open-ended


class Question(BaseModel):
    id: str  # "q_" + attribute
    attribute: str
    question: str
    input_type: InputType
    options: list[str] = Field(default_factory=list)
    ranges: list[RangeOption] = Field(default_factory=list)  # for input_type == range
    required_for_assessment: bool = False
    why_asked: str
    related_scheme_ids: list[str] = Field(default_factory=list)
    sensitivity: Sensitivity
    status: AnswerState = AnswerState.unanswered
    allow_prefer_not_to_answer: bool = True


class DocStatus(str, Enum):
    have = "have"
    obtained = "obtained"
    dont_have = "dont_have"
    needed = "needed"
    unknown = "unknown"


class ChecklistItem(BaseModel):
    id: str  # document id, e.g. "doc_income_certificate"
    name: str
    status: DocStatus
    order: int  # 1-based position in the plan
    required_by_scheme_ids: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)  # document ids (plan §5.4)
    source_urls: list[str] = Field(default_factory=list)
    reason: str
    issuing_authority: Optional[str] = None
    is_unknown: bool = False


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str = "document"  # "document" | "scheme"
    type: Optional[str] = None  # "document" | "scheme"
    status: Optional[str] = None  # for documents: have / dont_have / unknown

    def model_post_init(self, __context: Any) -> None:
        if self.type is None:
            self.type = self.kind
        if self.kind is None and self.type is not None:
            self.kind = self.type


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str = "required_for"  # or "prerequisite_of"
    type: Optional[str] = None  # "scheme requires document" | "document requires document"
    source_url: str = Field(min_length=1)  # edges without a source are never created

    def model_post_init(self, __context: Any) -> None:
        if self.type is None:
            if self.relation == "required_for":
                self.type = "scheme requires document"
            elif self.relation == "prerequisite_of":
                self.type = "document requires document"
            else:
                self.type = self.relation


class RankedDocument(BaseModel):
    priority: int
    doc_id: str
    name: str
    status: str  # "dont_have" | "unknown"
    schemes_helped: list[str] = Field(default_factory=list)
    scheme_names: list[str] = Field(default_factory=list)
    helps_count: int = 0
    summary: str = ""


class ActionPlan(BaseModel):
    checklist: list[ChecklistItem] = Field(default_factory=list)
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    ranking: list[RankedDocument] = Field(default_factory=list)
    shared_prerequisites: list[str] = Field(default_factory=list)  # doc ids needed by 2+ schemes
    explanation: str
    warnings: list[str] = Field(default_factory=list)
    excluded_documents: list[str] = Field(default_factory=list)  # names dropped for lacking a source
    mermaid: Optional[str] = None

    def to_graph_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.model_dump(mode="json") for n in self.nodes],
            "edges": [e.model_dump(mode="json") for e in self.edges],
            "ranking": [r.model_dump(mode="json") for r in self.ranking],
        }
