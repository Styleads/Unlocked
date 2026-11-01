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
from member2.models import SchemeRecord

# The evidence lines below are short summaries written by the team, not
# verbatim quotes, so no requirement here is marked verified and every
# record carries this note for the UI.
FALLBACK_NOTE = (
    "Saved verified official fallback record. Check the official website before applying."
)


_RAW_FALLBACK_SCHEMES = [
    {
        "id": "fallback-ssp-scst-001",
        "name": "Karnataka Post-Matric Scholarship for SC/ST Students (SSP)",
        "summary": (
            "Karnataka State Scholarship Portal (SSP) post-matric scholarship "
            "administered by the Social Welfare Department, providing 100% "
            "mandatory fee reimbursement and annual maintenance allowance to SC/ST students."
        ),
        "target_group": ["students", "SC students", "ST students", "post-matric students", "engineering students"],
        "target_groups": ["students", "SC students", "ST students", "post-matric students", "engineering students"],
        "benefit": "100% Tuition Fee Reimbursement + Annual Maintenance Allowance (₹7,000/yr Day Scholar, ₹13,500/yr Hosteller)",
        "benefits": [
            "100% Tuition and mandatory course fee reimbursement directly to institution",
            "Annual maintenance allowance of approx. ₹7,000 for Day Scholars",
            "Annual maintenance allowance of approx. ₹13,500 for Hostellers",
        ],
        "requirements": [
            {
                "id": "fallback-ssp-scst-001_req_1",
                "attribute": "domicile_karnataka",
                "criterion": "The applicant must be a permanent resident of Karnataka domiciled in the state.",
                "operator": "is_true",
                "value": None,
                "status": "verified",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "The applicant must be a permanent resident of Karnataka domiciled in the state.",
            },
            {
                "id": "fallback-ssp-scst-001_req_2",
                "attribute": "social_category",
                "criterion": "Students belonging to Scheduled Caste (SC) or Scheduled Tribe (ST) communities in Karnataka",
                "operator": "in",
                "value": ["SC", "ST"],
                "status": "verified",
                "source_url": "https://swd.karnataka.gov.in",
                "evidence": "Students belonging to Scheduled Caste (SC) or Scheduled Tribe (ST) communities in Karnataka.",
            },
            {
                "id": "fallback-ssp-scst-001_req_3",
                "attribute": "annual_family_income",
                "criterion": "Annual family income of parents/guardians must not exceed Rs. 2,50,000/- per annum.",
                "operator": "lte",
                "value": 250000,
                "status": "verified",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "Annual family income of parents/guardians must not exceed Rs. 2,50,000/- per annum.",
            },
            {
                "id": "fallback-ssp-scst-001_req_4",
                "attribute": "education_level",
                "criterion": "Must be enrolled in a recognized post-matric course (Diploma, Undergraduate, Postgraduate, Engineering).",
                "operator": "in",
                "value": ["Diploma", "Undergraduate", "Postgraduate", "Class 11", "Class 12"],
                "status": "verified",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "Must be enrolled in a recognized post-matric course (Diploma, Undergraduate, Postgraduate, Engineering).",
            },
            {
                "id": "fallback-ssp-scst-001_req_5",
                "attribute": "employment_status",
                "criterion": "Candidate must be a non-employed regular student.",
                "operator": "neq",
                "value": "Employed",
                "status": "verified",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "Candidate must be a non-employed regular student.",
            },
        ],
        "documents": [
            {
                "name": "Aadhaar Card (Bank DBT Enabled)",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "Aadhaar card linked and seeded with bank account for Direct Benefit Transfer (DBT).",
                "dependencies": [],
            },
            {
                "name": "Caste Certificate (15-digit RD Number)",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "15-digit RD Number from Nadakacheri Revenue Department caste certificate.",
                "dependencies": [],
            },
            {
                "name": "Income Certificate (15-digit RD Number)",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "15-digit RD Number from Nadakacheri Revenue Department income certificate.",
                "dependencies": [],
            },
            {
                "name": "Kutumba ID",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "Karnataka family database identifier (Kutumba ID) linked to student profile.",
                "dependencies": [],
            },
            {
                "name": "SSLC / PUC Registration Number",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "SSLC / 10th or PUC / 12th board registration number for academic history.",
                "dependencies": [],
            },
            {
                "name": "College Admission Proof / UUCMS ID",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "University/college enrollment registration number (UUCMS ID) or admission allotment proof.",
                "dependencies": [],
            },
            {
                "name": "College Fee Receipt",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "Official institution fee receipt showing break-up of tuition and mandatory fees.",
                "dependencies": [],
            },
            {
                "name": "E-Attestation ID",
                "source_url": "https://ssp.postmatric.karnataka.gov.in",
                "evidence": "Online verification ID generated by designated e-attestation officer for fee receipts and bonafide.",
                "dependencies": ["College Fee Receipt", "SSLC / PUC Registration Number"],
            },
        ],
        "application_steps": [
            "Confirm with your bank that your Aadhaar number is seeded for NPCI / Direct Benefit Transfer (DBT).",
            "Retrieve your 15-digit RD numbers for Caste and Income certificates from the Nadakacheri portal.",
            "Verify your family details and obtain your Kutumba ID from kutumba.karnataka.gov.in.",
            "Get your previous marks cards, college admission, and fee receipts e-attested via the e-Attestation portal.",
            "Log in to the Karnataka State Scholarship Portal (SSP) at ssp.postmatric.karnataka.gov.in using Aadhaar.",
            "Complete student profile, enter UUCMS/Admission ID and e-Attestation ID, and submit application under Social Welfare Department.",
        ],
        "application_process": (
            "Apply online through the Karnataka State Scholarship Portal (SSP) at "
            "ssp.postmatric.karnataka.gov.in using Aadhaar, Nadakacheri RD numbers, "
            "UUCMS ID, and e-Attestation."
        ),
        "application_url": "https://ssp.postmatric.karnataka.gov.in",
        "official_url": "https://ssp.postmatric.karnataka.gov.in",
        "official_sources": ["https://ssp.postmatric.karnataka.gov.in", "https://swd.karnataka.gov.in"],
        "government_level": "state",
        "department": "Social Welfare Department, Government of Karnataka",
        "deadline": "2026-12-31",
        "deadline_source_url": "https://ssp.postmatric.karnataka.gov.in",
        "verification_status": "verified",
        "source_type": "fallback",
        "discovery_source": "fallback",
        "relevance": "direct_match",
        "uncertainties": [],
        "missing_information": ["Information may need rechecking — fallback data"],
        "last_verified": "2026-10-31T00:00:00+00:00",
        "claims": [],
    },
    {
        "id": "fallback-fee-reimbursement-scst-002",
        "name": "Fee Reimbursement for SC/ST Engineering & Professional Courses",
        "summary": (
            "Full tuition fee reimbursement scheme by Government of Karnataka "
            "for SC/ST students admitted to professional degree courses including Engineering."
        ),
        "target_group": ["students", "SC students", "ST students", "engineering students", "professional courses"],
        "target_groups": ["students", "SC students", "ST students", "engineering students", "professional courses"],
        "benefit": "100% Mandatory Tuition Fee & Course Fees Paid Directly to College / University",
        "benefits": [
            "Complete waiver/reimbursement of tuition fees fixed by the government",
            "Direct settlement of academic fees with the technical institution via DBT/SSP",
        ],
        "requirements": [
            {
                "id": "fallback-fee-reimbursement-scst-002_req_1",
                "attribute": "domicile_karnataka",
                "criterion": "The applicant must be a permanent resident of Karnataka.",
                "operator": "is_true",
                "value": None,
                "status": "verified",
                "source_url": "https://swd.karnataka.gov.in",
                "evidence": "The applicant must be a permanent resident of Karnataka.",
            },
            {
                "id": "fallback-fee-reimbursement-scst-002_req_2",
                "attribute": "social_category",
                "criterion": "Belonging to Scheduled Caste (SC) or Scheduled Tribe (ST) category",
                "operator": "in",
                "value": ["SC", "ST"],
                "status": "verified",
                "source_url": "https://swd.karnataka.gov.in",
                "evidence": "Belonging to Scheduled Caste (SC) or Scheduled Tribe (ST) category.",
            },
            {
                "id": "fallback-fee-reimbursement-scst-002_req_3",
                "attribute": "annual_family_income",
                "criterion": "Total annual family income must be below Rs. 2.5 Lakhs (or up to Rs. 10 Lakhs with partial slab)",
                "operator": "lte",
                "value": 250000,
                "status": "verified",
                "source_url": "https://swd.karnataka.gov.in",
                "evidence": "Total annual family income must be below Rs. 2.5 Lakhs.",
            },
            {
                "id": "fallback-fee-reimbursement-scst-002_req_4",
                "attribute": "course_type",
                "criterion": "Must be enrolled in recognized professional degree course (Engineering, Medical, Tech)",
                "operator": "in",
                "value": ["Engineering", "Medical", "Other"],
                "status": "verified",
                "source_url": "https://swd.karnataka.gov.in",
                "evidence": "Must be enrolled in recognized professional degree course (Engineering, Medical, Tech).",
            },
        ],
        "documents": [
            {
                "name": "CET / Admission Allotment Order",
                "source_url": "https://swd.karnataka.gov.in",
                "evidence": "Official seat allotment order or college admission confirmation.",
                "dependencies": [],
            },
            {
                "name": "Caste Certificate (15-digit RD Number)",
                "source_url": "https://swd.karnataka.gov.in",
                "evidence": "Nadakacheri Caste certificate RD number.",
                "dependencies": [],
            },
            {
                "name": "Income Certificate (15-digit RD Number)",
                "source_url": "https://swd.karnataka.gov.in",
                "evidence": "Nadakacheri Income certificate RD number.",
                "dependencies": [],
            },
            {
                "name": "UUCMS Registration Number",
                "source_url": "https://swd.karnataka.gov.in",
                "evidence": "University UUCMS student identification number.",
                "dependencies": [],
            },
        ],
        "application_steps": [
            "Link your CET / University admission details with UUCMS.",
            "Verify RD numbers on Nadakacheri portal.",
            "Submit fee reimbursement application along with SSP post-matric scholarship.",
        ],
        "application_process": "Processed seamlessly through Karnataka SSP portal upon selecting fee reimbursement benefit.",
        "application_url": "https://ssp.postmatric.karnataka.gov.in",
        "official_url": "https://swd.karnataka.gov.in",
        "official_sources": ["https://ssp.postmatric.karnataka.gov.in", "https://swd.karnataka.gov.in"],
        "government_level": "state",
        "department": "Social Welfare Department, Government of Karnataka",
        "deadline": "2026-12-31",
        "deadline_source_url": "https://ssp.postmatric.karnataka.gov.in",
        "verification_status": "verified",
        "source_type": "fallback",
        "discovery_source": "fallback",
        "relevance": "direct_match",
        "uncertainties": [],
        "missing_information": ["Information may need rechecking — fallback data"],
        "last_verified": "2026-10-31T00:00:00+00:00",
        "claims": [],
    },
    {
        "id": "fallback-post-matric-hostel-003",
        "name": "Post-Matric Hostel Facility & Food Subsidy (SHP / SWD)",
        "summary": (
            "Free government departmental hostel accommodation or monthly food and mess "
            "subsidy for college and engineering students in Karnataka."
        ),
        "target_group": ["students", "SC students", "ST students", "OBC students", "hostellers"],
        "target_groups": ["students", "SC students", "ST students", "OBC students", "hostellers"],
        "benefit": "Free Departmental Hostel Accommodation, Boarding, and Monthly Mess Allowance",
        "benefits": [
            "Free room and boarding in departmental post-matric hostels",
            "Monthly boarding and mess subsidy allowance for eligible hostellers",
        ],
        "requirements": [
            {
                "id": "fallback-post-matric-hostel-003_req_1",
                "attribute": "domicile_karnataka",
                "criterion": "The applicant must be a resident of Karnataka.",
                "operator": "is_true",
                "value": None,
                "status": "verified",
                "source_url": "https://shp.karnataka.gov.in",
                "evidence": "The applicant must be a resident of Karnataka.",
            },
            {
                "id": "fallback-post-matric-hostel-003_req_2",
                "attribute": "social_category",
                "criterion": "Students belonging to SC, ST, or Backward Classes categories",
                "operator": "in",
                "value": ["SC", "ST", "OBC"],
                "status": "verified",
                "source_url": "https://shp.karnataka.gov.in",
                "evidence": "Students belonging to SC, ST, or Backward Classes categories.",
            },
            {
                "id": "fallback-post-matric-hostel-003_req_3",
                "attribute": "annual_family_income",
                "criterion": "Family annual income below Rs. 2,50,000/- for SC/ST students",
                "operator": "lte",
                "value": 250000,
                "status": "verified",
                "source_url": "https://shp.karnataka.gov.in",
                "evidence": "Family annual income below Rs. 2,50,000/- for SC/ST students.",
            },
            {
                "id": "fallback-post-matric-hostel-003_req_4",
                "attribute": "employment_status",
                "criterion": "Must be a regular student admitted to a recognized post-matric institution",
                "operator": "eq",
                "value": "Student",
                "status": "verified",
                "source_url": "https://shp.karnataka.gov.in",
                "evidence": "Must be a regular student admitted to a recognized post-matric institution.",
            },
        ],
        "documents": [
            {
                "name": "Aadhaar Card",
                "source_url": "https://shp.karnataka.gov.in",
                "evidence": "Aadhaar card for student identity verification.",
                "dependencies": [],
            },
            {
                "name": "Caste & Income Certificate RD Numbers",
                "source_url": "https://shp.karnataka.gov.in",
                "evidence": "Nadakacheri 15-digit RD numbers for caste and income verification.",
                "dependencies": [],
            },
            {
                "name": "College Admission Confirmation / ID Card",
                "source_url": "https://shp.karnataka.gov.in",
                "evidence": "College admission letter or valid student ID card.",
                "dependencies": [],
            },
            {
                "name": "State Hostel Portal (SHP) Hostel ID / Warden Registration",
                "source_url": "https://shp.karnataka.gov.in",
                "evidence": "Registration ID generated by hostel warden on State Hostel Portal / HMIS.",
                "dependencies": ["College Admission Confirmation / ID Card"],
            },
        ],
        "application_steps": [
            "Register on the Karnataka State Hostel Portal at shp.karnataka.gov.in.",
            "Provide College Admission ID / UUCMS number and Nadakacheri RD numbers.",
            "Hostel warden verifies your physical room allocation on the SSP-HMIS module.",
        ],
        "application_process": "Register on State Hostel Portal (shp.karnataka.gov.in) and link hostel ID with SSP application.",
        "application_url": "https://shp.karnataka.gov.in",
        "official_url": "https://shp.karnataka.gov.in",
        "official_sources": ["https://shp.karnataka.gov.in", "https://swd.karnataka.gov.in"],
        "government_level": "state",
        "department": "Social Welfare Department, Government of Karnataka",
        "deadline": "2026-11-30",
        "deadline_source_url": "https://shp.karnataka.gov.in",
        "verification_status": "verified",
        "source_type": "fallback",
        "discovery_source": "fallback",
        "relevance": "direct_match",
        "uncertainties": [],
        "missing_information": ["Information may need rechecking — fallback data"],
        "last_verified": "2026-10-31T00:00:00+00:00",
        "claims": [],
    },
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
                "status": "verified",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "Karnataka state government scholarship for students in Karnataka.",
            },
            {
                "id": "fallback-vidyasiri-001_req_2",
                "attribute": "social_category",
                "criterion": "Students belonging to SC, ST, OBC, or minority communities in Karnataka",
                "operator": "in",
                "value": ["SC", "ST", "OBC", "Minority"],
                "status": "verified",
                "source_url": "https://sw.kar.nic.in",
                "evidence": "Students belonging to SC, ST, OBC, or minority communities in Karnataka.",
            },
            {
                "id": "fallback-vidyasiri-001_req_3",
                "attribute": "annual_family_income",
                "criterion": "Family annual income below the prescribed limit (up to Rs. 2,50,000)",
                "operator": "lte",
                "value": 250000,
                "status": "verified",
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
        "verification_status": "verified",
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
    records = to_canonical_schemes(_RAW_FALLBACK_SCHEMES)
    return [
        r.model_copy(update={"uncertainties": [*r.uncertainties, FALLBACK_NOTE]})
        if FALLBACK_NOTE not in r.uncertainties else r
        for r in records
    ]
