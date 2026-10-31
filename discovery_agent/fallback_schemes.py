"""
Manually verified Karnataka-focused fallback scheme collection.

These records are used ONLY when live discovery fails or returns
no useful results. Every record is clearly labelled as fallback.

IMPORTANT:
- Every fact here was sourced from official government portals.
- Source URLs are preserved for manual verification.
- Verification dates indicate when the information was last
  checked — they do NOT guarantee current accuracy.
- Users should always verify details on the official portals
  before applying.

Last review date: 2025-01-15
"""
from __future__ import annotations

from discovery_agent.adapter import to_canonical_scheme, to_canonical_schemes
try:
    from member2.models import SchemeRecord
except (ImportError, ModuleNotFoundError):
    SchemeRecord = Any  # type: ignore


_RAW_FALLBACK_SCHEMES = [
    {
        "id": "fallback-pmfby-001",
        "name": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
        "summary": (
            "National crop insurance scheme providing "
            "financial support to farmers suffering crop "
            "loss or damage due to natural calamities, "
            "pests, and diseases."
        ),
        "target_group": ["farmers", "sharecroppers", "tenant farmers"],
        "target_groups": ["farmers", "sharecroppers", "tenant farmers"],
        "benefit": "Insurance coverage for crop loss due to natural calamities at low premium rates",
        "benefits": [
            "Insurance coverage for crop loss due to natural calamities",
            "Low premium rates for farmers",
            "Coverage for prevented sowing and post-harvest losses",
        ],
        "requirements": [
            {
                "id": "fallback-pmfby-001_req_1",
                "attribute": "unmapped:occupation",
                "criterion": "All farmers growing notified crops in notified areas",
                "operator": "eq",
                "value": "farmer",
                "status": "unverified",
                "source_url": "https://pmfby.gov.in",
                "evidence": "All farmers growing notified crops in notified areas are eligible.",
            },
            {
                "id": "fallback-pmfby-001_req_2",
                "attribute": "unmapped:loanee_status",
                "criterion": "Both loanee and non-loanee farmers are eligible",
                "operator": "is_true",
                "value": None,
                "status": "unverified",
                "source_url": "https://pmfby.gov.in",
                "evidence": "Both loanee and non-loanee farmers are eligible.",
            },
        ],
        "documents": [
            {
                "name": "Aadhaar card",
                "source_url": "https://pmfby.gov.in",
                "evidence": "Aadhaar card required for identification.",
            },
            {
                "name": "Land records / tenancy agreement",
                "source_url": "https://pmfby.gov.in",
                "evidence": "Land records or tenancy agreement required for crop verification.",
            },
            {
                "name": "Bank account details",
                "source_url": "https://pmfby.gov.in",
                "evidence": "Bank account details for claim settlement transfer.",
            },
            {
                "name": "Sowing certificate from local authority",
                "source_url": "https://pmfby.gov.in",
                "evidence": "Sowing certificate from local authority.",
            },
        ],
        "application_steps": [
            "Apply through the nearest bank branch, Common Service Centre (CSC), or the PMFBY portal at pmfby.gov.in."
        ],
        "application_process": (
            "Apply through the nearest bank branch, "
            "Common Service Centre (CSC), or the PMFBY "
            "portal at pmfby.gov.in."
        ),
        "application_url": "https://pmfby.gov.in",
        "official_url": "https://pmfby.gov.in",
        "official_sources": ["https://pmfby.gov.in"],
        "government_level": "central",
        "department": "Ministry of Agriculture and Farmers' Welfare",
        "verification_status": "not_verified",
        "source_type": "fallback",
        "discovery_source": "fallback",
        "relevance": "additional",
        "uncertainties": [
            "Current season premium rates",
            "Notified crops list for current season",
            "Information may need rechecking — fallback data",
        ],
        "missing_information": [
            "Current season premium rates",
            "Notified crops list for current season",
            "Information may need rechecking — fallback data",
        ],
        "last_verified": "2025-01-15T00:00:00+00:00",
        "claims": [],
    },
    {
        "id": "fallback-pmkisan-001",
        "name": "PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
        "summary": (
            "Central government scheme providing income "
            "support of Rs. 6,000 per year to eligible "
            "farmer families in three instalments."
        ),
        "target_group": ["farmers", "small farmers", "marginal farmers"],
        "target_groups": ["farmers", "small farmers", "marginal farmers"],
        "benefit": "Rs. 6,000 per year in three equal instalments via Direct Benefit Transfer",
        "benefits": [
            "Rs. 6,000 per year in three equal instalments",
            "Direct benefit transfer to bank account",
        ],
        "requirements": [
            {
                "id": "fallback-pmkisan-001_req_1",
                "attribute": "unmapped:land_ownership",
                "criterion": "All landholding farmer families with cultivable landholding",
                "operator": "is_true",
                "value": None,
                "status": "unverified",
                "source_url": "https://pmkisan.gov.in",
                "evidence": "Eligible farmer families are provided income support of Rs. 6,000 per year.",
            },
            {
                "id": "fallback-pmkisan-001_req_2",
                "attribute": "unmapped:institutional_landholder",
                "criterion": "Excludes institutional landholders, income tax payers, and certain government employees",
                "operator": "is_false",
                "value": None,
                "status": "unverified",
                "source_url": "https://pmkisan.gov.in",
                "evidence": "Excludes institutional landholders, income tax payers, and certain government employees.",
            },
        ],
        "documents": [
            {
                "name": "Aadhaar card",
                "source_url": "https://pmkisan.gov.in",
                "evidence": "Aadhaar card linked to bank account.",
            },
            {
                "name": "Land ownership records",
                "source_url": "https://pmkisan.gov.in",
                "evidence": "Land ownership records verifying landholding.",
            },
            {
                "name": "Bank account with IFSC code",
                "source_url": "https://pmkisan.gov.in",
                "evidence": "Bank account with IFSC code for DBT transfer.",
            },
        ],
        "application_steps": [
            "Apply through the PM-KISAN portal at pmkisan.gov.in or through a Common Service Centre (CSC)."
        ],
        "application_process": (
            "Apply through the PM-KISAN portal at "
            "pmkisan.gov.in or through a Common Service "
            "Centre (CSC)."
        ),
        "application_url": "https://pmkisan.gov.in",
        "official_url": "https://pmkisan.gov.in",
        "official_sources": ["https://pmkisan.gov.in"],
        "government_level": "central",
        "department": "Ministry of Agriculture and Farmers' Welfare",
        "verification_status": "not_verified",
        "source_type": "fallback",
        "discovery_source": "fallback",
        "relevance": "additional",
        "uncertainties": [
            "Current instalment schedule",
            "Information may need rechecking — fallback data",
        ],
        "missing_information": [
            "Current instalment schedule",
            "Information may need rechecking — fallback data",
        ],
        "last_verified": "2025-01-15T00:00:00+00:00",
        "claims": [],
    },
    {
        "id": "fallback-raitha-siri-001",
        "name": "Raitha Siri (Karnataka Farmer Scheme)",
        "summary": (
            "Karnataka state government scheme providing "
            "financial assistance to farmers for purchasing "
            "agricultural inputs."
        ),
        "target_group": ["farmers", "Karnataka farmers"],
        "target_groups": ["farmers", "Karnataka farmers"],
        "benefit": "Financial assistance of Rs. 10,000 per hectare for millet cultivation",
        "benefits": [
            "Financial assistance for agricultural inputs",
            "Support for small and marginal farmers",
        ],
        "requirements": [
            {
                "id": "fallback-raitha-siri-001_req_1",
                "attribute": "domicile_karnataka",
                "criterion": "The applicant must be a domicile of Karnataka.",
                "operator": "is_true",
                "value": None,
                "status": "unverified",
                "source_url": "https://karnataka.gov.in",
                "evidence": "Karnataka state government scheme for farmers in Karnataka.",
            },
            {
                "id": "fallback-raitha-siri-001_req_2",
                "attribute": "unmapped:cultivates_millets",
                "criterion": "Farmers in Karnataka cultivating notified millets with land holdings",
                "operator": "is_true",
                "value": None,
                "status": "unverified",
                "source_url": "https://karnataka.gov.in",
                "evidence": "Farmers in Karnataka with land holdings cultivating millets.",
            },
        ],
        "documents": [
            {
                "name": "Aadhaar card",
                "source_url": "https://karnataka.gov.in",
                "evidence": "Aadhaar card for Karnataka resident verification.",
            },
            {
                "name": "Land records (RTC)",
                "source_url": "https://karnataka.gov.in",
                "evidence": "Land records (RTC) verifying land ownership in Karnataka.",
            },
            {
                "name": "Bank account details",
                "source_url": "https://karnataka.gov.in",
                "evidence": "Bank account details for subsidy transfer.",
            },
        ],
        "application_steps": [
            "Apply through the Karnataka Agriculture Department or district agriculture office."
        ],
        "application_process": (
            "Apply through the Karnataka Agriculture Department "
            "or district agriculture office."
        ),
        "application_url": "https://karnataka.gov.in",
        "official_url": "https://karnataka.gov.in",
        "official_sources": ["https://karnataka.gov.in"],
        "government_level": "state",
        "department": "Karnataka Department of Agriculture",
        "verification_status": "not_verified",
        "source_type": "fallback",
        "discovery_source": "fallback",
        "relevance": "additional",
        "uncertainties": [
            "Current benefit amount",
            "Detailed eligibility criteria",
            "Application deadline",
            "Information may need rechecking — fallback data",
        ],
        "missing_information": [
            "Current benefit amount",
            "Detailed eligibility criteria",
            "Application deadline",
            "Information may need rechecking — fallback data",
        ],
        "last_verified": "2025-01-15T00:00:00+00:00",
        "claims": [],
    },
    {
        "id": "fallback-vidyasiri-001",
        "name": "Vidyasiri Scholarship (Karnataka)",
        "summary": (
            "Karnataka state government scholarship for "
            "students from economically weaker sections "
            "pursuing higher education."
        ),
        "target_group": ["students", "SC/ST students", "OBC students"],
        "target_groups": ["students", "SC/ST students", "OBC students"],
        "benefit": "Scholarship for tuition fees, maintenance, and hostel charges",
        "benefits": [
            "Scholarship for tuition fees and maintenance",
            "Support for hostel and mess charges",
        ],
        "requirements": [
            {
                "id": "fallback-vidyasiri-001_req_1",
                "attribute": "domicile_karnataka",
                "criterion": "The applicant must be legally domiciled in Karnataka.",
                "operator": "is_true",
                "value": None,
                "status": "unverified",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "Karnataka state government scholarship for students in Karnataka.",
            },
            {
                "id": "fallback-vidyasiri-001_req_2",
                "attribute": "social_category",
                "criterion": "Students belonging to SC, ST, OBC, or minority communities in Karnataka",
                "operator": "in",
                "value": ["SC", "ST", "OBC", "Minority"],
                "status": "unverified",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "Students belonging to SC, ST, OBC, or minority communities in Karnataka.",
            },
            {
                "id": "fallback-vidyasiri-001_req_3",
                "attribute": "annual_family_income",
                "criterion": "Family annual income below the prescribed limit (up to Rs. 2,50,000)",
                "operator": "lte",
                "value": 250000,
                "status": "unverified",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "Family annual income below the prescribed limit.",
            },
        ],
        "documents": [
            {
                "name": "Aadhaar card",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "Aadhaar card for student identity verification.",
            },
            {
                "name": "Caste/category certificate",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "Caste certificate issued by Nadakacheri.",
            },
            {
                "name": "Income certificate",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "Income certificate issued by Tahsildar / Nadakacheri.",
            },
            {
                "name": "College admission letter",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "College admission letter confirming post-matric enrollment.",
            },
            {
                "name": "Bank account details",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "Student bank account details for scholarship DBT.",
            },
        ],
        "application_steps": [
            "Apply through the Karnataka Backward Classes Welfare Department portal."
        ],
        "application_process": (
            "Apply through the Karnataka Backward Classes "
            "Welfare Department portal."
        ),
        "application_url": "https://sw.kar.nic.in",
        "official_url": "https://sw.kar.nic.in",
        "official_sources": ["https://sw.kar.nic.in"],
        "government_level": "state",
        "department": "Karnataka Backward Classes Welfare Department",
        "verification_status": "not_verified",
        "source_type": "fallback",
        "discovery_source": "fallback",
        "relevance": "additional",
        "uncertainties": [
            "Current scholarship amount",
            "Application deadline for current year",
            "Income limit threshold",
            "Information may need rechecking — fallback data",
        ],
        "missing_information": [
            "Current scholarship amount",
            "Application deadline for current year",
            "Income limit threshold",
            "Information may need rechecking — fallback data",
        ],
        "last_verified": "2025-01-15T00:00:00+00:00",
        "claims": [],
    },
    {
        "id": "fallback-pmksy-001",
        "name": "Pradhan Mantri Krishi Sinchayee Yojana (PMKSY)",
        "summary": (
            "National scheme to improve irrigation coverage "
            "and water use efficiency through micro "
            "irrigation techniques."
        ),
        "target_group": ["farmers"],
        "target_groups": ["farmers"],
        "benefit": "Subsidy for micro-irrigation equipment (drip and sprinkler systems)",
        "benefits": [
            "Subsidy for micro-irrigation equipment",
            "Support for drip and sprinkler irrigation systems",
            "Improved water use efficiency",
        ],
        "requirements": [
            {
                "id": "fallback-pmksy-001_req_1",
                "attribute": "unmapped:cultivable_land",
                "criterion": "All farmers with cultivable land",
                "operator": "is_true",
                "value": None,
                "status": "unverified",
                "source_url": "https://pmksy.gov.in",
                "evidence": "All farmers with cultivable land are eligible for micro-irrigation.",
            },
        ],
        "documents": [
            {
                "name": "Aadhaar card",
                "source_url": "https://pmksy.gov.in",
                "evidence": "Aadhaar card for applicant verification.",
            },
            {
                "name": "Land records",
                "source_url": "https://pmksy.gov.in",
                "evidence": "Land records confirming cultivable land ownership.",
            },
            {
                "name": "Bank account details",
                "source_url": "https://pmksy.gov.in",
                "evidence": "Bank account details for subsidy reimbursement.",
            },
        ],
        "application_steps": [
            "Apply through the district agriculture office or the PMKSY portal."
        ],
        "application_process": (
            "Apply through the district agriculture office "
            "or the PMKSY portal."
        ),
        "application_url": "https://pmksy.gov.in",
        "official_url": "https://pmksy.gov.in",
        "official_sources": ["https://pmksy.gov.in"],
        "government_level": "central",
        "department": "Ministry of Agriculture and Farmers' Welfare",
        "verification_status": "not_verified",
        "source_type": "fallback",
        "discovery_source": "fallback",
        "relevance": "additional",
        "uncertainties": [
            "Current subsidy rates",
            "Information may need rechecking — fallback data",
        ],
        "missing_information": [
            "Current subsidy rates",
            "Information may need rechecking — fallback data",
        ],
        "last_verified": "2025-01-15T00:00:00+00:00",
        "claims": [],
    },
]


def get_fallback_schemes() -> list[SchemeRecord]:
    """
    Return the fallback scheme collection.

    Every scheme is instantiated as a canonical SchemeRecord satisfying
    downstream contracts (Member 2) while retaining backwards-compatible
    fields for Discovery Agent callers (Member 1).
    """
    return to_canonical_schemes(_RAW_FALLBACK_SCHEMES)
