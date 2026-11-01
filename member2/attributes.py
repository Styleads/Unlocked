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

FUNDING_RANGES = [
    RangeOption(label="Up to ₹50,000 (Micro / Shishu)", min=0, max=50_000),
    RangeOption(label="₹50,000 – ₹1,00,000 (Vishwakarma Tranche 1)", min=50_001, max=100_000),
    RangeOption(label="₹1,00,000 – ₹2,00,000 (Vishwakarma Tranche 2)", min=100_001, max=200_000),
    RangeOption(label="₹2,00,000 – ₹5,00,000 (MUDRA Kishore / Udyogini)", min=200_001, max=500_000),
    RangeOption(label="₹5,00,000 – ₹10,00,000 (MUDRA Tarun)", min=500_001, max=1_000_000),
    RangeOption(label="Above ₹10,00,000 (Stand-Up India)", min=1_000_001, max=None),
]

_SPECS = [
    AttributeSpec(
        id="state",
        label="State of residence",
        input_type=InputType.select,
        options=[
            "Karnataka", "Haryana", "Maharashtra", "Tamil Nadu", "Andhra Pradesh",
            "Kerala", "Telangana", "Punjab", "Gujarat", "Rajasthan", "Uttar Pradesh",
            "West Bengal", "Delhi", "Other"
        ],
        sensitivity=Sensitivity.low,
        effort=0,
        question="Which state do you live in?",
        why_template="Most schemes are run by a state or apply only to its residents.",
        aliases=["state of residence", "resident state", "state"],
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
        aliases=["employment status", "work status", "job seeker", "employment type"],
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
        aliases=[
            "domicile",
            "karnataka domicile",
            "native of karnataka",
            "domicile of karnataka",
            "karnataka",
            "in karnataka",
            "resident in karnataka",
            "karnataka resident",
            "resident of karnataka",
            "permanent resident of karnataka",
        ],
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
        # Pensions domain (DECISIONS #67): old-age, widow and disability pensions
        # usually exclude people already drawing another government pension.
        id="receives_other_pension",
        label="Receiving another government pension",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=0,
        question="Are you currently receiving any other pension from the government?",
        why_template="Most pension schemes cannot be combined with another government pension.",
        aliases=["other pension", "availing other pension", "any other pension"],
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
    AttributeSpec(
        id="domicile_state",
        label="State of domicile",
        input_type=InputType.select,
        options=[
            "Karnataka", "Haryana", "Maharashtra", "Tamil Nadu", "Andhra Pradesh",
            "Kerala", "Telangana", "Punjab", "Gujarat", "Rajasthan", "Uttar Pradesh",
            "West Bengal", "Delhi", "Other"
        ],
        sensitivity=Sensitivity.low,
        effort=0,
        question="Which state are you legally domiciled in?",
        why_template="Most state welfare schemes require permanent domicile in the administering state.",
        aliases=["domicile state", "state of domicile", "permanent resident of", "domicile of"],
    ),
    AttributeSpec(
        id="citizenship",
        label="Citizenship",
        input_type=InputType.select,
        options=["Indian", "Other"],
        sensitivity=Sensitivity.low,
        effort=0,
        question="Are you a citizen of India?",
        why_template="Government schemes require Indian citizenship.",
        aliases=["citizenship", "indian citizen", "citizen of india", "nationality", "citizenship status"],
    ),
    AttributeSpec(
        id="occupation",
        label="Primary occupation or traditional trade",
        input_type=InputType.text,
        sensitivity=Sensitivity.low,
        effort=0,
        question="What is your primary occupation or traditional trade?",
        why_template="Schemes such as PM Vishwakarma and artisan programmes are designed for specific traditional trades and livelihoods.",
        aliases=["occupation", "trade", "traditional trade", "artisan trade", "craftsperson", "primary occupation", "profession", "tailor", "tailoring", "artisan"],
    ),
    AttributeSpec(
        id="business_ownership",
        label="Business ownership and operating structure",
        input_type=InputType.select,
        options=["Individual / Sole Proprietorship", "Partnership", "Private Limited / Corporate", "None"],
        sensitivity=Sensitivity.low,
        effort=0,
        question="Is your business operated by you as an individual rather than through a registered company?",
        why_template="MUDRA, PM Vishwakarma and Udyogini are intended for individual proprietors, micro-enterprises and artisans rather than corporate entities.",
        aliases=["business ownership", "ownership structure", "non-corporate small business segment", "non corporate small business", "business segment", "enterprise type", "business structure", "operating structure"],
    ),
    AttributeSpec(
        id="is_micro_enterprise",
        label="Micro or small enterprise operation",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=0,
        question="Do you currently operate a small business or provide a service through your own business?",
        why_template="MUDRA and micro-enterprise loans support self-employed individuals running small businesses in services, manufacturing, trading or agri-allied activities.",
        aliases=["micro enterprise", "small enterprise", "micro or small enterprise", "micro/small enterprises in manufacturing, services, trading or agri-allied", "micro small enterprises in manufacturing services trading or agri allied", "small business operation"],
    ),
    AttributeSpec(
        id="landholding_hectares",
        label="Agricultural landholding",
        input_type=InputType.number,
        unit="hectares",
        sensitivity=Sensitivity.low,
        effort=1,
        question="How many hectares of agricultural land do you or your family own?",
        why_template="Agricultural assistance and farmer schemes (like PM-KISAN) have landholding criteria.",
        aliases=["landholding", "landholding hectares", "agricultural land", "cultivable land", "land owned"],
    ),
    AttributeSpec(
        id="loan_purpose",
        label="Loan purpose",
        input_type=InputType.select,
        options=["Working capital", "Machinery or equipment purchase", "Business expansion", "Setting up a new enterprise"],
        sensitivity=Sensitivity.low,
        effort=0,
        question="What will the loan funds primarily be used for?",
        why_template="Credit schemes distinguish working capital support from equipment/machinery purchase and new business setup.",
        aliases=["loan purpose", "purpose of loan", "purpose of funding", "funding purpose", "use of loan"],
    ),
    AttributeSpec(
        id="funding_amount_needed",
        label="Funding or loan amount needed",
        input_type=InputType.range,
        ranges=FUNDING_RANGES,
        unit="INR",
        sensitivity=Sensitivity.medium,
        effort=0,
        question="How much funding or loan assistance does your business require?",
        why_template="Different credit schemes offer distinct loan brackets (e.g. MUDRA Shishu up to ₹50,000, Vishwakarma up to ₹1-2 Lakh, Udyogini up to ₹3 Lakh).",
        aliases=["funding amount", "funding amount needed", "loan amount", "loan requirement", "amount of funding"],
    ),
    AttributeSpec(
        id="business_stage",
        label="Business stage",
        input_type=InputType.select,
        options=["Existing Business", "New Business (Greenfield)"],
        sensitivity=Sensitivity.low,
        effort=0,
        question="Is this for expanding an existing business or setting up a brand new venture (greenfield project)?",
        why_template="Some schemes like Stand-Up India are exclusively for greenfield projects, while PM Vishwakarma requires an existing traditional trade.",
        aliases=["business stage", "green field projects only", "greenfield project", "greenfield", "new business or existing", "first time venture"],
    ),
    AttributeSpec(
        id="previous_government_loan",
        label="Previous government credit-linked loan",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=0,
        question="Have you availed a credit-linked loan under government schemes (such as PMEGP, PM SVANidhi, or MUDRA) in the past 5 years?",
        why_template="PM Vishwakarma and other credit schemes restrict beneficiaries who have existing loans under similar government programmes.",
        aliases=["previous government loan", "availed loans under similar credit based schemes", "prior government loan", "existing pmegp loan", "credit based schemes of central or state government"],
    ),
    AttributeSpec(
        id="has_bank_default",
        label="Default on bank loans",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=0,
        question="Are you or your business currently in default with any bank or financial institution?",
        why_template="Bank-linked credit schemes require that the applicant is not an active defaulter.",
        aliases=["bank default", "borrower should not be in default", "not in default", "defaulter", "default to any bank financial institution"],
    ),
    AttributeSpec(
        id="family_member_beneficiary",
        label="Scheme benefits already received in family",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=0,
        question="Has anyone else in your immediate family or household already received benefits under this scheme?",
        why_template="Schemes like PM Vishwakarma and certain welfare grants restrict benefits to one member per family.",
        aliases=["family benefit", "one member of the family", "family member beneficiary", "restricted to one member of the family"],
    ),
    AttributeSpec(
        id="central_obc_ncl",
        label="Central OBC Non-Creamy Layer status",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.medium,
        effort=1,
        question="Do you possess a Central OBC Non-Creamy Layer (OBC-NCL) certificate issued by the competent authority?",
        why_template="Central government schemes require inclusion in the Central OBC list and non-creamy layer certification, which is distinct from state OBC categories.",
        aliases=["central obc", "central obc ncl", "obc ncl", "central list obc", "central obc non creamy layer"],
    ),
    AttributeSpec(
        id="karnataka_caste_category",
        label="Karnataka caste reservation category",
        input_type=InputType.select,
        options=["Category 1", "Category 2A", "Category 2B", "Category 3A", "Category 3B", "SC", "ST", "General"],
        sensitivity=Sensitivity.high,
        effort=0,
        question="Which specific Karnataka reservation category do you belong to (e.g. Cat-1, 2A, 2B, 3A, 3B)?",
        why_template="Karnataka state schemes and scholarships have distinct income thresholds and quotas for Category 1, 2A, 2B, 3A, and 3B.",
        aliases=["karnataka caste category", "karnataka category", "karnataka reservation category", "category 2a", "category 1", "category 3a", "category 3b", "category 2b"],
    ),
    AttributeSpec(
        id="viable_business_plan",
        label="Viable business proposal or project report",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=1,
        question="Do you have a business proposal or project idea describing your operations and funding needs?",
        why_template="Banks evaluate a business proposal during loan appraisal to assess viability and repayment capacity.",
        aliases=["viable business plan", "business plan", "project report", "project proposal"],
    ),
    AttributeSpec(
        id="portal_registration",
        label="Portal registration or enrolment",
        input_type=InputType.boolean,
        sensitivity=Sensitivity.low,
        effort=0,
        question="Have you already completed registration or enrolment on the official portal?",
        why_template="Portal registration is an enrolment procedure required before official processing.",
        aliases=["portal registration", "registered on portal", "registration on portal", "registration status", "scheme registration", "enrolment on portal"],
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


# Canonical Indian States catalog
INDIAN_STATES = {
    "andhra pradesh": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chhattisgarh": "Chhattisgarh",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal pradesh": "Himachal Pradesh",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "west bengal": "West Bengal",
    "delhi": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir",
    "ladakh": "Ladakh",
    "puducherry": "Puducherry",
    "chandigarh": "Chandigarh",
}


def detect_state_in_text(text: Optional[str]) -> Optional[str]:
    """Identify if text refers to an Indian state, returning canonical state title."""
    if not text or not isinstance(text, str):
        return None
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", text.lower())
    words = set(cleaned.split())
    # Multi-word states first
    for state_key, canonical in INDIAN_STATES.items():
        if " " in state_key:
            if state_key in cleaned:
                return canonical
        elif state_key in words:
            return canonical
    return None


# Canonical Karnataka districts catalog
KARNATAKA_DISTRICTS = {
    "bagalkot", "ballari", "bellary", "belagavi", "belgaum", "bengaluru",
    "bengaluru urban", "bengaluru rural", "bangalore", "bidar",
    "chamarajanagar", "chikkaballapur", "chikkamagaluru", "chikmagalur",
    "chitradurga", "dakshina kannada", "mangalore", "mangaluru", "davanagere",
    "dharwad", "gadag", "hassan", "haveri", "kalaburagi", "gulbarga",
    "kodagu", "coorg", "kolar", "koppal", "mandya", "mysuru", "mysore",
    "raichur", "ramanagara", "shivamogga", "shimoga", "tumakuru", "tumkur",
    "udupi", "uttara kannada", "karwar", "vijayapura", "bijapur",
    "vijayanagara", "yadgir",
}


def is_karnataka_district(district_name: Optional[str]) -> bool:
    """Return True if district belongs to Karnataka."""
    if not district_name or not isinstance(district_name, str):
        return False
    norm = normalize_text(district_name)
    return norm in KARNATAKA_DISTRICTS or any(d in norm for d in KARNATAKA_DISTRICTS)


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
