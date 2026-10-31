"""Canonical user-attribute registry.

Every requirement must resolve to one of these ids so the same fact, worded
differently across schemes, becomes a single question. Vocabulary only: nothing
here states what any real scheme requires.
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from .models import InputType, RangeOption, Sensitivity


class AttributeSpec(BaseModel):
    id: str
    label: str
    input_type: InputType
    options: list[str] = Field(default_factory=list)
    ranges: list[RangeOption] = Field(default_factory=list)
    unit: Optional[str] = None
    sensitivity: Sensitivity
    effort: int = Field(ge=0, le=2)  # 0 = trivial, 2 = may need to look it up
    question: str
    why_template: str
    aliases: list[str] = Field(default_factory=list)
    # True when a rewrite could change the legal meaning, so the LLM never rephrases it.
    keep_wording: bool = False


# Both ends inclusive (DECISIONS.md #9), so bands must not share a boundary.
INCOME_RANGES = [
    RangeOption(label="Below ₹1 lakh", min=0, max=99_999),
    RangeOption(label="₹1 lakh – ₹2.5 lakh", min=100_000, max=250_000),
    RangeOption(label="₹2.5 lakh – ₹5 lakh", min=250_001, max=500_000),
    RangeOption(label="₹5 lakh – ₹8 lakh", min=500_001, max=800_000),
    RangeOption(label="Above ₹8 lakh", min=800_001, max=None),
]

_SPECS = [
    AttributeSpec(
        id="state",
        label="State of residence",
        input_type=InputType.select,
        options=["Karnataka", "Other"],
        sensitivity=Sensitivity.low,
        effort=0,
        question="Which state do you live in?",
        why_template="Most schemes are run by a state or apply only to its residents.",
        aliases=["state of residence", "resident state"],
    ),
    AttributeSpec(
        id="district",
        label="District",
        input_type=InputType.text,
        sensitivity=Sensitivity.low,
        effort=0,
        question="Which district do you live in?",
        why_template="Some schemes are limited to particular districts.",
        aliases=["district of residence", "taluk"],
    ),
    AttributeSpec(
        id="age",
        label="Age",
        input_type=InputType.number,
        unit="years",
        sensitivity=Sensitivity.medium,
        effort=0,
        question="How old are you?",
        why_template="Many schemes have minimum or maximum age limits.",
        aliases=["age limit", "age of applicant", "applicant age", "age group"],
    ),
    AttributeSpec(
        id="gender",
        label="Gender",
        input_type=InputType.select,
        options=["Female", "Male", "Other"],
        sensitivity=Sensitivity.medium,
        effort=0,
        question="What is your gender?",
        why_template="Some schemes are specifically for women or other groups.",
        aliases=["sex", "female applicant", "women", "girl student"],
    ),
    AttributeSpec(
        id="education_level",
        label="Current education level",
        input_type=InputType.select,
        options=["Class 10", "Class 12", "Diploma", "Undergraduate", "Postgraduate", "Not studying"],
        sensitivity=Sensitivity.low,
        effort=0,
        question="What are you studying now, or what is the highest level you completed?",
        why_template="Schemes are usually tied to a particular stage of education.",
        aliases=["education", "course level", "qualification", "level of study", "class"],
    ),
    AttributeSpec(
        id="course_type",
        label="Course type",
        input_type=InputType.select,
        options=["Engineering", "Medical", "Arts/Science/Commerce", "Other"],
        sensitivity=Sensitivity.low,
        effort=0,
        question="What kind of course are you studying?",
        why_template="Some schemes cover only certain courses, such as professional degrees.",
        aliases=["course", "stream", "field of study", "professional course"],
    ),
    AttributeSpec(
        id="year_of_study",
        label="Year of study",
        input_type=InputType.number,
        sensitivity=Sensitivity.low,
        effort=0,
        question="Which year of your course are you in?",
        why_template="Some schemes are only for first-year students or for renewals.",
        aliases=["current year", "academic year", "first year", "year of course"],
    ),
    AttributeSpec(
        id="institution_type",
        label="Type of institution",
        input_type=InputType.select,
        options=["Government", "Aided", "Private"],
        sensitivity=Sensitivity.low,
        effort=0,
        question="Is your college or school government, government-aided, or private?",
        why_template="Some benefits apply only to certain kinds of institution.",
        aliases=["college type", "type of college", "institution", "type of institution"],
    ),
    AttributeSpec(
        id="annual_family_income",
        label="Annual family income",
        input_type=InputType.range,
        ranges=INCOME_RANGES,
        unit="INR",
        sensitivity=Sensitivity.high,
        effort=1,
        question="What is your family's approximate total yearly income?",
        why_template="Many schemes set an income limit. A rough range is enough.",
        aliases=[
            "family income",
            "annual income",
            "household income",
            "parental income",
            "income limit",
            "income ceiling",
            "income",  # Agent 1's related_attribute name
        ],
    ),
    AttributeSpec(
        id="social_category",
        label="Social category",
        input_type=InputType.select,
        options=["General", "SC", "ST", "OBC", "Other"],
        sensitivity=Sensitivity.high,
        effort=0,
        question="Which social category do you belong to?",
        why_template="Several schemes reserve benefits for specific categories.",
        aliases=["caste", "category", "caste category", "community", "reserved category"],
    ),
    AttributeSpec(
        id="is_minority",
        label="Minority community",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.high,
        effort=0,
        question="Do you belong to a notified minority community?",
        why_template="Some scholarships are open only to notified minority communities.",
        aliases=["minority", "minority status", "religious minority", "minority community"],
    ),
    AttributeSpec(
        id="has_disability",
        label="Disability",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.high,
        effort=0,
        question="Do you have a disability that is certified, or that you could get certified?",
        why_template="Some schemes offer extra support for persons with disabilities.",
        aliases=["disability", "pwd", "person with disability", "differently abled", "divyang"],
    ),
    AttributeSpec(
        id="employment_status",
        label="Employment status",
        input_type=InputType.select,
        options=["Student", "Employed", "Self-employed", "Unemployed", "Other"],
        sensitivity=Sensitivity.medium,
        effort=0,
        question="Which best describes your current work situation?",
        why_template="Some schemes are for students, job seekers, or workers only.",
        aliases=["occupation", "work status", "job seeker"],
    ),
    AttributeSpec(
        id="previous_year_marks_percent",
        label="Marks in last qualifying exam",
        input_type=InputType.number,
        unit="%",
        sensitivity=Sensitivity.medium,
        effort=1,
        question="Roughly what percentage did you score in your last exam?",
        why_template="Some scholarships require a minimum score.",
        aliases=["marks", "percentage", "minimum marks", "marks percentage", "previous year marks"],
    ),
    AttributeSpec(
        id="domicile_karnataka",
        label="Domicile in Karnataka",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=1,
        # Legal domicile, distinct from current state of residence (DECISIONS.md #12).
        question="Are you legally domiciled in Karnataka (not just currently living there)?",
        keep_wording=True,
        why_template="Many state schemes require Karnataka domicile, not just current residence.",
        aliases=["domicile", "karnataka domicile", "native of karnataka", "domicile of karnataka"],
    ),
    AttributeSpec(
        id="receives_other_scholarship",
        label="Receiving another scholarship",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=0,
        question="Are you currently receiving any other scholarship?",
        why_template="Some schemes cannot be combined with other scholarships.",
        aliases=["other scholarship", "availing other scholarship", "any other scholarship"],
    ),
    AttributeSpec(
        id="residence_area",
        label="Rural or urban residence",
        input_type=InputType.select,
        options=["Rural", "Urban"],
        sensitivity=Sensitivity.low,
        effort=0,
        question="Do you live in a rural or an urban area?",
        why_template="Some schemes differ for rural and urban residents.",
        aliases=["rural", "urban", "area of residence", "rural area"],
    ),
    AttributeSpec(
        id="household_card_type",
        label="Ration card type",
        input_type=InputType.select,
        options=["BPL", "APL", "Antyodaya", "None"],
        sensitivity=Sensitivity.medium,
        effort=1,
        question="What type of ration card does your household have, if any?",
        why_template="Some schemes use the ration card type as proof of economic need.",
        aliases=["ration card", "bpl", "bpl card", "below poverty line", "ration card type"],
    ),
]

ATTRIBUTES: dict[str, AttributeSpec] = {s.id: s for s in _SPECS}

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    """Lowercase, punctuation and underscores to single spaces."""
    return _NON_WORD.sub(" ", text.lower()).strip()


def _build_alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for spec in _SPECS:
        for key in (spec.id, spec.label, *spec.aliases):
            norm = normalize_text(key)
            # An alias claimed twice would silently misroute requirements.
            if index.setdefault(norm, spec.id) != spec.id:
                raise ValueError(f"alias {key!r} maps to more than one attribute")
    return index


_ALIAS_INDEX = _build_alias_index()


def is_canonical(attribute_id: Optional[str]) -> bool:
    return attribute_id in ATTRIBUTES


def resolve_attribute(name: str) -> Optional[str]:
    """Exact match on id, label or alias after normalization. No fuzzy guessing:
    a miss means the requirement needs clarification."""
    return _ALIAS_INDEX.get(normalize_text(name))


# --- a scheme's own conditions -----------------------------------------------
# A verified rule no registry attribute fits ("at least 2 of Physics, Chemistry,
# ..."; "listed in the PUC-II merit list") is asked as a yes/no question quoting
# the rule, so it can be answered instead of blocking the scheme (DECISIONS #63).

CONDITION_PREFIX = "unmapped:"


def is_condition(attribute: Optional[str]) -> bool:
    return bool(attribute) and attribute.startswith(CONDITION_PREFIX)


def condition_spec(attribute: str, text: str = "") -> AttributeSpec:
    shown = str(text or attribute[len(CONDITION_PREFIX):])
    if "_" in shown and " " not in shown:  # an id like "citizen_of_india", not prose
        shown = shown.replace("_", " ")
    shown = " ".join(shown.split())
    if len(shown) > 160:
        shown = shown[:157].rstrip() + "..."
    return AttributeSpec(
        id=attribute,
        label="a condition of this scheme",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=1,
        question=f'Does this apply to you: "{shown}"?',
        why_template="This is one of the scheme's own conditions, from its official page.",
        keep_wording=True,  # quoted rule text: never rephrased
    )
