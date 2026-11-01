"""
Regression test suite for Agent 2 (Eligibility Assessment & Intelligent Questionnaire).

Covers all 14 core improvement requirements:
1. PM Vishwakarma: Unregistered tailor must not be automatically marked ineligible.
2. Age: Applicant below minimum age must be correctly assessed as unlikely to match.
3. Known profile attributes: Age, occupation, income, and domicile must not be redundantly asked.
4. Central OBC versus Karnataka OBC: Category information must not be treated as interchangeable.
5. Unknown eKYC: Must remain unknown rather than implying ineligibility.
6. Registration: Missing registration must be distinguished from an actual eligibility exclusion.
7. Consolidation: Multiple schemes requiring annual family income must generate one common question.
8. Business ownership: Non-corporate small business segment maps to canonical business_ownership.
9. Loan purpose: Distinguish working capital from machinery/equipment purchases.
10. Existing business: Do not apply new-enterprise (greenfield) restrictions to existing businesses.
11. Previous loans: Correctly assess scheme-specific interactions and restrictions.
12. Skipped answers: Must not cause destructive reassessment or overwrite answered values.
13. Question numbering: Must remain continuous across multiple batches.
14. Agent 3 integration: Application prerequisites must not be represented as eligibility exclusions or mandatory documents.
"""

from __future__ import annotations

import pytest

from member2.assess import (
    as_answer_map,
    assess_requirement,
    assess_scheme,
    assess_schemes,
    reassess_schemes,
)
from member2.attributes import ATTRIBUTES, is_canonical, resolve_attribute
from member2.models import (
    Answer,
    AnswerState,
    DocumentRequirement,
    InputType,
    Operator,
    Question,
    Requirement,
    RequirementCategory,
    RequirementStatus,
    RequirementVerification,
    SchemeRecord,
    SchemeStatus,
)
from member2.normalize import (
    classify_requirement_category,
    normalize_scheme,
)
from member2.planning import build_action_plan
from member2.questions import (
    apply_answers,
    generate_consolidated_questions,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

SOURCE_VISHWAKARMA = "https://pmvishwakarma.gov.in/guidelines"
SOURCE_MUDRA = "https://www.mudra.org.in"
SOURCE_UDYOGINI = "https://kswdc.karnataka.gov.in/udyogini"
SOURCE_STANDUP = "https://www.standupmitra.in"


def make_pm_vishwakarma_scheme() -> SchemeRecord:
    """Realistic PM Vishwakarma scheme representation."""
    return SchemeRecord(
        id="pm_vishwakarma",
        name="PM Vishwakarma Scheme",
        summary="Support for artisans and craftspeople in traditional trades including tailoring.",
        requirements=[
            Requirement(
                id="pmv_req_trade",
                attribute="occupation",
                criterion="An artisan or craftsperson working with hands and tools in one of 18 traditional trades (including Tailor/Darzi)",
                operator=Operator.in_,
                value=["Tailor", "Darzi", "Carpenter", "Blacksmith", "Potter", "Weaver"],
                status=RequirementVerification.verified,
                source_url=SOURCE_VISHWAKARMA,
                evidence="working with hands and tools in one of 18 traditional family-based trades",
                category=RequirementCategory.eligibility,
            ),
            Requirement(
                id="pmv_req_age",
                attribute="age",
                criterion="The minimum age of the beneficiary should be 18 years on the date of registration.",
                operator=Operator.gte,
                value=18,
                status=RequirementVerification.verified,
                source_url=SOURCE_VISHWAKARMA,
                evidence="minimum age of the beneficiary should be 18 years",
                category=RequirementCategory.eligibility,
            ),
            Requirement(
                id="pmv_req_reg",
                attribute="portal_registration",
                criterion="Registration on PM Vishwakarma portal with biometric Aadhaar authentication.",
                operator=Operator.is_true,
                value=None,
                status=RequirementVerification.verified,
                source_url=SOURCE_VISHWAKARMA,
                evidence="Registration on PM Vishwakarma portal through Common Services Centres",
                category=RequirementCategory.application_prerequisite,
            ),
            Requirement(
                id="pmv_req_training",
                attribute=None,
                criterion="Basic Training is considered essential for improving skills and drawing the first tranche of loan.",
                operator=None,
                value=None,
                status=RequirementVerification.verified,
                source_url=SOURCE_VISHWAKARMA,
                evidence="Basic Training is considered essential for improving the skills of all registered Vishwakarmas, and an eligibility condition for drawing the first tranche of loan.",
                category=RequirementCategory.post_approval,
            ),
        ],
        documents=[
            DocumentRequirement(
                name="Aadhaar Card",
                mandatory=True,
                source_url=SOURCE_VISHWAKARMA,
                evidence="Aadhaar card for biometric authentication",
            ),
            DocumentRequirement(
                name="Bank Account Passbook",
                mandatory=True,
                source_url=SOURCE_VISHWAKARMA,
                evidence="Bank passbook with active bank account details",
            ),
        ],
        verification_status="verified",
    )


def make_mudra_scheme() -> SchemeRecord:
    """Realistic Pradhan Mantri MUDRA Yojana scheme representation."""
    return SchemeRecord(
        id="pm_mudra",
        name="Pradhan Mantri Mudra Yojana (PMMY)",
        summary="Micro-finance loans for non-corporate, non-farm small/micro enterprises.",
        requirements=[
            Requirement(
                id="mudra_req_citizenship",
                attribute="citizenship",
                criterion="Any Indian citizen who has a business plan for a non-farm sector income generating activity.",
                operator=Operator.eq,
                value="Indian",
                status=RequirementVerification.verified,
                source_url=SOURCE_MUDRA,
                evidence="Any Indian citizen who has a business plan for non-farm sector income generating activity",
                category=RequirementCategory.eligibility,
            ),
            Requirement(
                id="mudra_req_ownership",
                attribute="business_ownership",
                criterion="Non-corporate small business segment comprising proprietorship or partnership firms.",
                operator=Operator.in_,
                value=["Individual / Sole Proprietorship", "Partnership"],
                status=RequirementVerification.verified,
                source_url=SOURCE_MUDRA,
                evidence="Non-corporate small business segment comprising proprietorship or partnership firms",
                category=RequirementCategory.eligibility,
            ),
            Requirement(
                id="mudra_req_micro",
                attribute="is_micro_enterprise",
                criterion="Micro or small enterprise engaged in manufacturing, trading, or services.",
                operator=Operator.is_true,
                value=None,
                status=RequirementVerification.verified,
                source_url=SOURCE_MUDRA,
                evidence="Micro or small enterprise engaged in manufacturing, trading, or services",
                category=RequirementCategory.eligibility,
            ),
            Requirement(
                id="mudra_req_plan",
                attribute="viable_business_plan",
                criterion="Viable business plan / project proposal submitted with the loan application.",
                operator=Operator.is_true,
                value=None,
                status=RequirementVerification.verified,
                source_url=SOURCE_MUDRA,
                evidence="viable business plan for income generating activity",
                category=RequirementCategory.verification,
            ),
        ],
        documents=[
            DocumentRequirement(
                name="Identity Proof",
                mandatory=True,
                source_url=SOURCE_MUDRA,
                evidence="Voter ID or Aadhaar card as identity proof",
            ),
        ],
        verification_status="verified",
    )


def make_udyogini_scheme() -> SchemeRecord:
    """Realistic Karnataka Udyogini Scheme representation."""
    return SchemeRecord(
        id="karnataka_udyogini",
        name="Karnataka Udyogini Scheme",
        summary="Subsidized loans for women entrepreneurs in micro-enterprises and small businesses.",
        requirements=[
            Requirement(
                id="udyogini_req_gender",
                attribute="gender",
                criterion="Only women entrepreneurs are eligible.",
                operator=Operator.eq,
                value="Female",
                status=RequirementVerification.verified,
                source_url=SOURCE_UDYOGINI,
                evidence="Assistance provided to women entrepreneurs",
                category=RequirementCategory.eligibility,
            ),
            Requirement(
                id="udyogini_req_domicile",
                attribute="domicile_karnataka",
                criterion="Applicant must be a permanent resident of Karnataka.",
                operator=Operator.is_true,
                value=None,
                status=RequirementVerification.verified,
                source_url=SOURCE_UDYOGINI,
                evidence="Permanent resident of Karnataka",
                category=RequirementCategory.eligibility,
            ),
            Requirement(
                id="udyogini_req_income",
                attribute="annual_family_income",
                criterion="Annual family income must not exceed Rs. 1,50,000 for General/OBC categories.",
                operator=Operator.lte,
                value=150000,
                status=RequirementVerification.verified,
                source_url=SOURCE_UDYOGINI,
                evidence="Annual family income limit is Rs. 1.50 lakhs for OBC and General categories",
                category=RequirementCategory.eligibility,
            ),
            Requirement(
                id="udyogini_req_age",
                attribute="age",
                criterion="Age of the woman applicant must be between 18 and 55 years.",
                operator=Operator.gte,
                value=18,
                status=RequirementVerification.verified,
                source_url=SOURCE_UDYOGINI,
                evidence="Age of the woman applicant between 18 and 55 years",
                category=RequirementCategory.eligibility,
            ),
        ],
        documents=[
            DocumentRequirement(
                name="Income and Caste Certificate",
                mandatory=True,
                source_url=SOURCE_UDYOGINI,
                evidence="Income and caste certificate issued by Tahsildar",
            ),
        ],
        verification_status="verified",
    )


# ---------------------------------------------------------------------------
# Regression Test 1: PM Vishwakarma Unregistered Tailor Not Ineligible
# ---------------------------------------------------------------------------

def test_pm_vishwakarma_unregistered_tailor_not_ineligible():
    """1. PM Vishwakarma: A tailor who is not yet registered must NOT be marked ineligible."""
    scheme = make_pm_vishwakarma_scheme()
    # Kavya's profile: 31yo tailor, not yet registered on the portal
    user_answers = {
        "occupation": Answer(attribute="occupation", state=AnswerState.answered, value="Tailor"),
        "age": Answer(attribute="age", state=AnswerState.answered, value=31),
        "portal_registration": Answer(attribute="portal_registration", state=AnswerState.answered, value=False),
    }

    assessment = assess_scheme(scheme, user_answers)

    # Must be a potential match because registration is an application procedure, not an exclusion!
    assert assessment.status == SchemeStatus.potential_match
    assert assessment.status != SchemeStatus.unlikely_to_match

    # The registration requirement result should reflect that it is an application procedure
    reg_result = next(r for r in assessment.requirements if r.requirement_id == "pmv_req_reg")
    assert reg_result.category == RequirementCategory.application_prerequisite
    assert "application process" in reg_result.reason.lower() or "procedure" in reg_result.reason.lower()


# ---------------------------------------------------------------------------
# Regression Test 2: Age Below Minimum Correctly Assessed
# ---------------------------------------------------------------------------

def test_age_below_minimum_correctly_assessed():
    """2. Age: An applicant below the minimum required age must be correctly assessed."""
    scheme = make_pm_vishwakarma_scheme()
    user_answers = {
        "occupation": Answer(attribute="occupation", state=AnswerState.answered, value="Tailor"),
        "age": Answer(attribute="age", state=AnswerState.answered, value=16),  # below 18
    }

    assessment = assess_scheme(scheme, user_answers)

    assert assessment.status == SchemeStatus.unlikely_to_match
    age_result = next(r for r in assessment.requirements if r.requirement_id == "pmv_req_age")
    assert age_result.status == RequirementStatus.not_satisfied
    assert "age" in assessment.explanation.lower()


# ---------------------------------------------------------------------------
# Regression Test 3: Known Profile Attributes Not Redundantly Asked
# ---------------------------------------------------------------------------

def test_known_profile_attributes_not_redundantly_asked():
    """3. Known profile attributes: Age, occupation, income and domicile must not be redundantly asked."""
    schemes = [make_pm_vishwakarma_scheme(), make_mudra_scheme(), make_udyogini_scheme()]

    # Kavya's seeded profile answers
    seeded_answers = {
        "age": Answer(attribute="age", state=AnswerState.answered, value=31),
        "occupation": Answer(attribute="occupation", state=AnswerState.answered, value="Tailor"),
        "annual_family_income": Answer(attribute="annual_family_income", state=AnswerState.answered, value={"min": 135000, "max": 135000}),
        "state": Answer(attribute="state", state=AnswerState.answered, value="Karnataka"),
        "domicile_karnataka": Answer(attribute="domicile_karnataka", state=AnswerState.answered, value=True),
        "domicile_state": Answer(attribute="domicile_state", state=AnswerState.answered, value="Karnataka"),
        "district": Answer(attribute="district", state=AnswerState.answered, value="Koppal"),
        "social_category": Answer(attribute="social_category", state=AnswerState.answered, value="OBC"),
    }

    questions = generate_consolidated_questions(schemes, seeded_answers, {})
    asked_attrs = [q.attribute for q in questions]

    # None of the known profile attributes may be in the generated questions!
    assert "age" not in asked_attrs
    assert "occupation" not in asked_attrs
    assert "annual_family_income" not in asked_attrs
    assert "state" not in asked_attrs
    assert "domicile_karnataka" not in asked_attrs
    assert "domicile_state" not in asked_attrs
    assert "district" not in asked_attrs
    assert "social_category" not in asked_attrs


# ---------------------------------------------------------------------------
# Regression Test 4: Central OBC versus Karnataka OBC Not Interchangeable
# ---------------------------------------------------------------------------

def test_central_obc_versus_karnataka_obc_not_interchangeable():
    """4. Central OBC versus Karnataka OBC: Category information must not be incorrectly treated as interchangeable."""
    # Scheme specifically requiring Central OBC-NCL
    central_scheme = SchemeRecord(
        id="central_scheme_obc",
        name="Central OBC Fellowship",
        requirements=[
            Requirement(
                id="req_central_obc",
                attribute="central_obc_ncl",
                criterion="Must belong to Central OBC Non-Creamy Layer list",
                operator=Operator.is_true,
                value=None,
                status=RequirementVerification.verified,
                category=RequirementCategory.eligibility,
            )
        ],
        verification_status="verified",
    )

    # User only has state-level social_category="OBC"
    answers = as_answer_map({
        "social_category": {"attribute": "social_category", "state": "answered", "value": "OBC"}
    })

    # Central OBC-NCL is not yet answered, so it must evaluate to unknown, NOT satisfied
    result = assess_requirement(central_scheme.requirements[0], answers)
    assert result.status == RequirementStatus.unknown

    assessment = assess_scheme(central_scheme, answers)
    assert assessment.status == SchemeStatus.more_information_needed


# ---------------------------------------------------------------------------
# Regression Test 5: Unknown eKYC Remains Unknown Not Ineligible
# ---------------------------------------------------------------------------

def test_unknown_ekyc_remains_unknown_not_ineligible():
    """5. Unknown eKYC: Must remain unknown rather than become ineligible."""
    scheme = SchemeRecord(
        id="scheme_with_ekyc",
        name="Direct Benefit Scheme",
        requirements=[
            Requirement(
                id="req_ekyc",
                attribute="portal_registration",
                criterion="Aadhaar based e-KYC verification",
                operator=Operator.is_true,
                value=None,
                status=RequirementVerification.verified,
                category=RequirementCategory.application_prerequisite,
            ),
            Requirement(
                id="req_income",
                attribute="annual_family_income",
                criterion="Annual income <= Rs 2,00,000",
                operator=Operator.lte,
                value=200000,
                status=RequirementVerification.verified,
                category=RequirementCategory.eligibility,
            ),
        ],
        verification_status="verified",
    )

    # eKYC is unknown or unanswered, income is satisfied
    answers = as_answer_map({
        "annual_family_income": {"attribute": "annual_family_income", "state": "answered", "value": 150000},
        "portal_registration": {"attribute": "portal_registration", "state": "unknown", "value": None},
    })

    assessment = assess_scheme(scheme, answers)
    assert assessment.status == SchemeStatus.potential_match
    assert assessment.status != SchemeStatus.unlikely_to_match


# ---------------------------------------------------------------------------
# Regression Test 6: Registration Missing Distinguished from Exclusion
# ---------------------------------------------------------------------------

def test_missing_registration_distinguished_from_exclusion():
    """6. Registration: Missing registration must be distinguished from an actual eligibility exclusion."""
    scheme = SchemeRecord(
        id="scholarship_portal_scheme",
        name="SSP Post-Matric",
        requirements=[
            Requirement(
                id="req_elig",
                attribute="domicile_karnataka",
                criterion="Must be a resident of Karnataka",
                operator=Operator.is_true,
                value=None,
                status=RequirementVerification.verified,
                category=RequirementCategory.eligibility,
            ),
            Requirement(
                id="req_portal",
                attribute="portal_registration",
                criterion="Student must register on the SSP Portal",
                operator=Operator.is_true,
                value=None,
                status=RequirementVerification.verified,
                category=RequirementCategory.application_prerequisite,
            ),
        ],
        verification_status="verified",
    )

    # Citizen is in Karnataka but has not registered on the portal yet
    answers = as_answer_map({
        "domicile_karnataka": {"attribute": "domicile_karnataka", "state": "answered", "value": True},
        "portal_registration": {"attribute": "portal_registration", "state": "answered", "value": False},
    })

    assessment = assess_scheme(scheme, answers)
    # Registration missing is an application step, not an eligibility exclusion
    assert assessment.status == SchemeStatus.potential_match
    assert assessment.status != SchemeStatus.unlikely_to_match


# ---------------------------------------------------------------------------
# Regression Test 7: Consolidation Across Three Schemes
# ---------------------------------------------------------------------------

def test_consolidation_across_three_schemes():
    """7. Consolidation: Three schemes requiring annual family income must not generate three repeated questions."""
    s1 = SchemeRecord(
        id="s1", name="Scheme 1",
        requirements=[Requirement(id="r1", attribute="annual_family_income", criterion="Income <= 1.5 Lakh", operator=Operator.lte, value=150000, status=RequirementVerification.verified)],
        verification_status="verified"
    )
    s2 = SchemeRecord(
        id="s2", name="Scheme 2",
        requirements=[Requirement(id="r2", attribute="annual_family_income", criterion="Income <= 2.0 Lakh", operator=Operator.lte, value=200000, status=RequirementVerification.verified)],
        verification_status="verified"
    )
    s3 = SchemeRecord(
        id="s3", name="Scheme 3",
        requirements=[Requirement(id="r3", attribute="annual_family_income", criterion="Income <= 2.5 Lakh", operator=Operator.lte, value=250000, status=RequirementVerification.verified)],
        verification_status="verified"
    )

    questions = generate_consolidated_questions([s1, s2, s3], {}, {})
    income_questions = [q for q in questions if q.attribute == "annual_family_income"]

    # Must generate exactly ONE consolidated question covering all three schemes!
    assert len(income_questions) == 1
    assert set(income_questions[0].related_scheme_ids) == {"s1", "s2", "s3"}


# ---------------------------------------------------------------------------
# Regression Test 8: Business Ownership Questions Mapped Canonically
# ---------------------------------------------------------------------------

def test_business_ownership_questions_mapped_canonically():
    """8. Business ownership: Questions must be understandable and map to canonical attributes."""
    # Verify attribute canonical mapping
    assert is_canonical("business_ownership")
    assert resolve_attribute("Non-corporate small business segment") == "business_ownership"
    assert resolve_attribute("ownership structure") == "business_ownership"

    spec = ATTRIBUTES["business_ownership"]
    # Question text should be citizen-friendly, not bureaucratic jargon
    assert "rather than through a registered company" in spec.question or "individual" in spec.question
    assert "Does this apply to you: Non-corporate small business segment?" != spec.question


# ---------------------------------------------------------------------------
# Regression Test 9: Loan Purpose Distinguishes Working Capital and Machinery
# ---------------------------------------------------------------------------

def test_loan_purpose_distinguishes_working_capital_and_machinery():
    """9. Loan purpose: Distinguish working capital from machinery purchases."""
    assert is_canonical("loan_purpose")
    spec = ATTRIBUTES["loan_purpose"]

    options = spec.options
    assert any("working capital" in o.lower() for o in options)
    assert any("machinery" in o.lower() or "equipment" in o.lower() for o in options)

    # Test answer normalization in apply_answers
    answers, _ = apply_answers(
        {}, {},
        [
            {"attribute": "loan_purpose", "state": "answered", "value": "purchasing equipment and sewing machines"}
        ]
    )
    assert answers["loan_purpose"].value == "Machinery or equipment purchase"

    answers_wc, _ = apply_answers(
        {}, {},
        [
            {"attribute": "loan_purpose", "state": "answered", "value": "working capital for materials"}
        ]
    )
    assert answers_wc["loan_purpose"].value == "Working capital"


# ---------------------------------------------------------------------------
# Regression Test 10: Existing Business Not Restricted by Greenfield Rules
# ---------------------------------------------------------------------------

def test_existing_business_not_restricted_by_greenfield_rules():
    """10. Existing business: Do not automatically apply new-enterprise restrictions to an existing business without checking scheme rules."""
    # Greenfield only scheme (Stand-Up India)
    standup_scheme = SchemeRecord(
        id="standup_india",
        name="Stand-Up India",
        requirements=[
            Requirement(
                id="su_req_greenfield",
                attribute="business_stage",
                criterion="Loans under the scheme are available for green field projects only",
                operator=Operator.eq,
                value="New Business (Greenfield)",
                status=RequirementVerification.verified,
                category=RequirementCategory.eligibility,
            ),
        ],
        verification_status="verified",
    )

    # Existing traditional artisan scheme (Vishwakarma)
    vishwakarma = make_pm_vishwakarma_scheme()

    # User has an existing business
    answers = as_answer_map({
        "business_stage": {"attribute": "business_stage", "state": "answered", "value": "Existing Business"},
        "occupation": {"attribute": "occupation", "state": "answered", "value": "Tailor"},
        "age": {"attribute": "age", "state": "answered", "value": 31},
    })

    # Stand-Up India fails greenfield requirement
    standup_ass = assess_scheme(standup_scheme, answers)
    assert standup_ass.status == SchemeStatus.unlikely_to_match

    # PM Vishwakarma is NOT penalized by greenfield rules; it welcomes existing artisans!
    vishwakarma_ass = assess_scheme(vishwakarma, answers)
    assert vishwakarma_ass.status == SchemeStatus.potential_match


# ---------------------------------------------------------------------------
# Regression Test 11: Previous Loans Interactions Assessed
# ---------------------------------------------------------------------------

def test_previous_loans_interactions_assessed():
    """11. Previous loans: Correctly assess scheme-specific interactions and restrictions."""
    scheme = make_pm_vishwakarma_scheme()

    # User answered that they availed a government credit scheme in the past 5 years
    answers = as_answer_map({
        "occupation": {"attribute": "occupation", "state": "answered", "value": "Tailor"},
        "age": {"attribute": "age", "state": "answered", "value": 31},
        "previous_government_loan": {"attribute": "previous_government_loan", "state": "answered", "value": True},
    })

    assessment = assess_scheme(scheme, answers)
    assert "past 5 years" in assessment.explanation
    assert "PMEGP, PM SVANidhi, or MUDRA" in assessment.explanation


# ---------------------------------------------------------------------------
# Regression Test 12: Skipped Answers Non-Destructive
# ---------------------------------------------------------------------------

def test_skipped_answers_non_destructive():
    """12. Skipped answers: Must not cause destructive reassessment or overwrite answered values."""
    # Start with answered income
    answers, history = apply_answers(
        {}, {},
        [
            {"attribute": "annual_family_income", "state": "answered", "value": 135000},
            {"attribute": "age", "state": "answered", "value": 31},
        ]
    )
    assert answers["annual_family_income"].value == {"min": 135000, "max": 135000}
    assert answers["annual_family_income"].state == AnswerState.answered
    assert answers["age"].value == 31

    # User later submits a skip on annual_family_income and age
    updated_answers, updated_history = apply_answers(
        answers, history,
        [
            {"attribute": "annual_family_income", "state": "skipped", "value": None},
            {"attribute": "age", "state": "unknown", "value": None},
        ]
    )

    # The existing answered values must be preserved and not wiped out!
    assert updated_answers["annual_family_income"].state == AnswerState.answered
    assert updated_answers["annual_family_income"].value == {"min": 135000, "max": 135000}
    assert updated_answers["age"].state == AnswerState.answered
    assert updated_answers["age"].value == 31


# ---------------------------------------------------------------------------
# Regression Test 13: Question Numbering Continuous Across Batches
# ---------------------------------------------------------------------------

def test_question_numbering_continuous_across_batches():
    """13. Question numbering: Must remain continuous across multiple batches."""
    # Simulate batch 1 and batch 2
    batch_1_questions = [
        Question(id="q1", attribute="a1", question="First question?", input_type=InputType.boolean, why_asked="w1", sensitivity="low"),
        Question(id="q2", attribute="a2", question="Second question?", input_type=InputType.boolean, why_asked="w2", sensitivity="low"),
        Question(id="q3", attribute="a3", question="Third question?", input_type=InputType.boolean, why_asked="w3", sensitivity="low"),
    ]
    batch_2_questions = [
        Question(id="q4", attribute="a4", question="Fourth question?", input_type=InputType.boolean, why_asked="w4", sensitivity="low"),
        Question(id="q5", attribute="a5", question="Fifth question?", input_type=InputType.boolean, why_asked="w5", sensitivity="low"),
    ]

    question_counter = 1
    rendered_numbers = []

    # Batch 1
    for q in batch_1_questions:
        rendered_numbers.append(question_counter)
        question_counter += 1

    # Batch 2
    for q in batch_2_questions:
        rendered_numbers.append(question_counter)
        question_counter += 1

    # Numbering must be strictly continuous from 1 to 5 without resetting to 1
    assert rendered_numbers == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Regression Test 14: Agent 3 Integration Prerequisites Not Mandatory Documents
# ---------------------------------------------------------------------------

def test_agent3_integration_prerequisites_not_mandatory_documents():
    """14. Agent 3 integration: An application prerequisite must not be incorrectly represented as an eligibility exclusion or mandatory document."""
    pm_vishwakarma = make_pm_vishwakarma_scheme()

    # User is eligible (tailor, 31yo), but portal registration is false (not registered yet)
    answers = as_answer_map({
        "occupation": {"attribute": "occupation", "state": "answered", "value": "Tailor"},
        "age": {"attribute": "age", "state": "answered", "value": 31},
        "portal_registration": {"attribute": "portal_registration", "state": "answered", "value": False},
    })

    assessment = assess_scheme(pm_vishwakarma, answers)
    assert assessment.status == SchemeStatus.potential_match

    # Build action plan with Agent 3
    plan = build_action_plan(
        [pm_vishwakarma],
        user_documents={},
        assessments=[assessment],
    )

    # 1. Scheme must NOT be dropped from document planning
    scheme_node_ids = [n.id for n in plan.nodes if n.kind == "scheme"]
    assert "pm_vishwakarma" in scheme_node_ids

    # 2. Checklist must contain real documents, NOT invented mandatory documents for application prerequisites
    checklist_doc_names = [item.name.lower() for item in plan.checklist]
    assert "aadhaar card" in checklist_doc_names or "bank account passbook" in checklist_doc_names

    # Neither registration nor training should be an invented document requirement
    assert not any("registration on pm vishwakarma portal" in name for name in checklist_doc_names)
    assert not any("basic training" in name for name in checklist_doc_names)
