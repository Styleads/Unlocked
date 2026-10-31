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

from discovery_agent.scheme_schema import (
    SchemeRecord,
    SourceEvidence,
    SchemeClaim,
    SchemeCriterion,
)


def get_fallback_schemes() -> list[SchemeRecord]:
    """
    Return the fallback scheme collection.

    Every scheme is labelled with discovery_source='fallback'
    and verification_status='unverified' because these records
    may be outdated.
    """
    return [
        SchemeRecord(
            id="fallback-pmfby-001",
            name="Pradhan Mantri Fasal Bima Yojana (PMFBY)",
            description=(
                "National crop insurance scheme providing "
                "financial support to farmers suffering crop "
                "loss or damage due to natural calamities, "
                "pests, and diseases."
            ),
            target_groups=["farmers", "sharecroppers", "tenant farmers"],
            benefits=[
                "Insurance coverage for crop loss due to natural calamities",
                "Low premium rates for farmers",
                "Coverage for prevented sowing and post-harvest losses",
            ],
            eligibility_criteria=[
                SchemeCriterion(
                    description="All farmers growing notified crops in notified areas",
                    related_attribute="occupation",
                    verification_status="unverified",
                ),
                SchemeCriterion(
                    description="Both loanee and non-loanee farmers are eligible",
                    verification_status="unverified",
                ),
            ],
            required_documents=[
                "Aadhaar card",
                "Land records / tenancy agreement",
                "Bank account details",
                "Sowing certificate from local authority",
            ],
            application_process=(
                "Apply through the nearest bank branch, "
                "Common Service Centre (CSC), or the PMFBY "
                "portal at pmfby.gov.in."
            ),
            application_url="https://pmfby.gov.in",
            official_url="https://pmfby.gov.in",
            government_level="central",
            department="Ministry of Agriculture and Farmers' Welfare",
            source_evidence=[
                SourceEvidence(
                    title="PMFBY Official Portal",
                    url="https://pmfby.gov.in",
                    excerpt=(
                        "Pradhan Mantri Fasal Bima Yojana provides "
                        "comprehensive crop insurance coverage."
                    ),
                    is_official=True,
                ),
            ],
            claims=[],
            verification_status="unverified",
            discovery_source="fallback",
            relevance="additional",
            match_reasons=[],
            missing_information=[
                "Current season premium rates",
                "Notified crops list for current season",
                "Information may need rechecking — fallback data",
            ],
            last_verified="2025-01-15T00:00:00+00:00",
        ),
        SchemeRecord(
            id="fallback-pmkisan-001",
            name="PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)",
            description=(
                "Central government scheme providing income "
                "support of Rs. 6,000 per year to eligible "
                "farmer families in three instalments."
            ),
            target_groups=["farmers", "small farmers", "marginal farmers"],
            benefits=[
                "Rs. 6,000 per year in three equal instalments",
                "Direct benefit transfer to bank account",
            ],
            eligibility_criteria=[
                SchemeCriterion(
                    description="All landholding farmer families",
                    related_attribute="land_ownership",
                    verification_status="unverified",
                ),
                SchemeCriterion(
                    description=(
                        "Excludes institutional landholders, "
                        "income tax payers, and certain "
                        "government employees"
                    ),
                    verification_status="unverified",
                ),
            ],
            required_documents=[
                "Aadhaar card",
                "Land ownership records",
                "Bank account with IFSC code",
            ],
            application_process=(
                "Apply through the PM-KISAN portal at "
                "pmkisan.gov.in or through a Common Service "
                "Centre (CSC)."
            ),
            application_url="https://pmkisan.gov.in",
            official_url="https://pmkisan.gov.in",
            government_level="central",
            department="Ministry of Agriculture and Farmers' Welfare",
            source_evidence=[
                SourceEvidence(
                    title="PM-KISAN Official Portal",
                    url="https://pmkisan.gov.in",
                    excerpt=(
                        "Under the scheme, eligible farmer families "
                        "are provided income support of Rs. 6,000 "
                        "per year."
                    ),
                    is_official=True,
                ),
            ],
            claims=[],
            verification_status="unverified",
            discovery_source="fallback",
            relevance="additional",
            match_reasons=[],
            missing_information=[
                "Current instalment schedule",
                "Information may need rechecking — fallback data",
            ],
            last_verified="2025-01-15T00:00:00+00:00",
        ),
        SchemeRecord(
            id="fallback-raitha-siri-001",
            name="Raitha Siri (Karnataka Farmer Scheme)",
            description=(
                "Karnataka state government scheme providing "
                "financial assistance to farmers for purchasing "
                "agricultural inputs."
            ),
            target_groups=["farmers", "Karnataka farmers"],
            benefits=[
                "Financial assistance for agricultural inputs",
                "Support for small and marginal farmers",
            ],
            eligibility_criteria=[
                SchemeCriterion(
                    description="Farmers in Karnataka with land holdings",
                    related_attribute="location",
                    verification_status="unverified",
                ),
            ],
            required_documents=[
                "Aadhaar card",
                "Land records (RTC)",
                "Bank account details",
            ],
            application_process=(
                "Apply through the Karnataka Agriculture Department "
                "or district agriculture office."
            ),
            official_url="https://karnataka.gov.in",
            government_level="state",
            department="Karnataka Department of Agriculture",
            source_evidence=[
                SourceEvidence(
                    title="Karnataka Government Portal",
                    url="https://karnataka.gov.in",
                    excerpt="",
                    is_official=True,
                ),
            ],
            claims=[],
            verification_status="unverified",
            discovery_source="fallback",
            relevance="additional",
            match_reasons=[],
            missing_information=[
                "Current benefit amount",
                "Detailed eligibility criteria",
                "Application deadline",
                "Information may need rechecking — fallback data",
            ],
            last_verified="2025-01-15T00:00:00+00:00",
        ),
        SchemeRecord(
            id="fallback-vidyasiri-001",
            name="Vidyasiri Scholarship (Karnataka)",
            description=(
                "Karnataka state government scholarship for "
                "students from economically weaker sections "
                "pursuing higher education."
            ),
            target_groups=["students", "SC/ST students", "OBC students"],
            benefits=[
                "Scholarship for tuition fees and maintenance",
                "Support for hostel and mess charges",
            ],
            eligibility_criteria=[
                SchemeCriterion(
                    description=(
                        "Students belonging to SC, ST, OBC, or "
                        "minority communities in Karnataka"
                    ),
                    related_attribute="education",
                    verification_status="unverified",
                ),
                SchemeCriterion(
                    description=(
                        "Family annual income below the prescribed limit"
                    ),
                    related_attribute="household",
                    verification_status="unverified",
                ),
            ],
            required_documents=[
                "Aadhaar card",
                "Caste/category certificate",
                "Income certificate",
                "College admission letter",
                "Bank account details",
            ],
            application_process=(
                "Apply through the Karnataka Backward Classes "
                "Welfare Department portal."
            ),
            official_url="https://sw.kar.nic.in",
            government_level="state",
            department=(
                "Karnataka Backward Classes Welfare Department"
            ),
            source_evidence=[
                SourceEvidence(
                    title="Karnataka Social Welfare Portal",
                    url="https://sw.kar.nic.in",
                    excerpt="",
                    is_official=True,
                ),
            ],
            claims=[],
            verification_status="unverified",
            discovery_source="fallback",
            relevance="additional",
            match_reasons=[],
            missing_information=[
                "Current scholarship amount",
                "Application deadline for current year",
                "Income limit threshold",
                "Information may need rechecking — fallback data",
            ],
            last_verified="2025-01-15T00:00:00+00:00",
        ),
        SchemeRecord(
            id="fallback-pmksy-001",
            name=(
                "Pradhan Mantri Krishi Sinchayee Yojana (PMKSY)"
            ),
            description=(
                "National scheme to improve irrigation coverage "
                "and water use efficiency through micro "
                "irrigation techniques."
            ),
            target_groups=["farmers"],
            benefits=[
                "Subsidy for micro-irrigation equipment",
                "Support for drip and sprinkler irrigation systems",
                "Improved water use efficiency",
            ],
            eligibility_criteria=[
                SchemeCriterion(
                    description="All farmers with cultivable land",
                    related_attribute="occupation",
                    verification_status="unverified",
                ),
            ],
            required_documents=[
                "Aadhaar card",
                "Land records",
                "Bank account details",
            ],
            application_process=(
                "Apply through the district agriculture office "
                "or the PMKSY portal."
            ),
            official_url="https://pmksy.gov.in",
            government_level="central",
            department="Ministry of Agriculture and Farmers' Welfare",
            source_evidence=[
                SourceEvidence(
                    title="PMKSY Official Portal",
                    url="https://pmksy.gov.in",
                    excerpt="",
                    is_official=True,
                ),
            ],
            claims=[],
            verification_status="unverified",
            discovery_source="fallback",
            relevance="additional",
            match_reasons=[],
            missing_information=[
                "Current subsidy rates",
                "Information may need rechecking — fallback data",
            ],
            last_verified="2025-01-15T00:00:00+00:00",
        ),
    ]

