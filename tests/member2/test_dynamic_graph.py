"""Comprehensive tests for dynamic, data-driven dependency graph generation.

Verifies:
1. Zero hardcoded scheme or document names in Python logic.
2. Multi-category data loading (Student and Farmer test scenarios from data files, plus novel category).
3. Plain-language questioning and document status flow (have, dont_have, unknown).
4. Edge and node generation with verified sources and correct types/statuses.
5. Priority ranking of missing documents matching Example 5.
6. User with all documents (all have, empty missing ranking, all green).
7. User with no documents (all dont_have, full ranking, all red).
8. Midway status update / answer change flow (graph & checklist regenerate dynamically).
9. Multi-format rendering: Mermaid (have=green, dont_have=red, unknown=grey) and Obsidian notes in scheme-map/.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from member2.agent3 import Agent3
from member2.data_loader import (
    list_available_categories,
    load_all_schemes,
    load_document_definitions,
    load_schemes_by_category,
    load_schemes_from_file,
)
from member2.models import DocStatus, SchemeRecord
from member2.planning import (
    build_action_plan,
    render_mermaid,
    render_obsidian_notes,
)


@pytest.fixture
def student_schemes():
    return load_schemes_by_category("students")


@pytest.fixture
def farmer_schemes():
    return load_schemes_by_category("farmers")


# ============================================================================
# 1. Multi-Category Data Loading & Zero Hardcoding Tests
# ============================================================================

def test_available_categories_discovered():
    cats = list_available_categories()
    assert "students" in cats
    assert "farmers" in cats


def test_load_all_schemes_from_data_dir():
    all_schemes = load_all_schemes()
    assert "students" in all_schemes
    assert "farmers" in all_schemes
    assert len(all_schemes["students"]) >= 2
    assert len(all_schemes["farmers"]) >= 2


def test_completely_novel_category_without_code_changes(tmp_path):
    """Proves that a completely new category (e.g. weavers) with novel document names
    works dynamically without touching any Python code."""
    novel_data = {
        "category": "weavers",
        "schemes": [
            {
                "id": "weaver_samman_scheme",
                "name": "Nekar Samman Yojana",
                "summary": "Financial support of Rs 5,000 for handloom and powerloom weavers.",
                "government_level": "state",
                "target_group": ["weavers"],
                "deadline": "2026-12-15",
                "deadline_source_url": "https://handlooms.karnataka.gov.in",
                "requirements": [
                    {
                        "id": "weaver_req_1",
                        "attribute": "weaver_registration",
                        "criterion": "Must be a registered weaver.",
                        "operator": "is_true",
                        "value": None,
                        "status": "verified",
                        "source_url": "https://handlooms.karnataka.gov.in/guidelines",
                        "evidence": "Registered weavers in Karnataka."
                    }
                ],
                "documents": [
                    {
                        "name": "Weaver Identity Card (Pehchan)",
                        "source_url": "https://handlooms.karnataka.gov.in/docs",
                        "evidence": "Pehchan card issued by Ministry of Textiles"
                    },
                    {
                        "name": "Loom Inspection Certificate",
                        "source_url": "https://handlooms.karnataka.gov.in/docs",
                        "evidence": "Physical inspection verification certificate",
                        "dependencies": [
                            {
                                "depends_on": "Weaver Identity Card (Pehchan)",
                                "source_url": "https://handlooms.karnataka.gov.in/docs"
                            }
                        ]
                    }
                ],
                "application_url": "https://handlooms.karnataka.gov.in",
                "official_sources": ["https://handlooms.karnataka.gov.in"],
                "verification_status": "verified",
                "source_type": "official"
            }
        ]
    }
    novel_file = tmp_path / "weavers.json"
    novel_file.write_text(json.dumps(novel_data), encoding="utf-8")

    schemes = load_schemes_from_file(novel_file)
    assert len(schemes) == 1
    assert schemes[0].name == "Nekar Samman Yojana"

    plan = build_action_plan(
        schemes,
        user_documents={"doc_weaver_identity_card_pehchan": "have"}
    )
    assert len(plan.checklist) == 2
    pehchan = next(c for c in plan.checklist if c.id == "doc_weaver_identity_card_pehchan")
    loom = next(c for c in plan.checklist if c.id == "doc_loom_inspection_certificate")

    assert pehchan.status == DocStatus.have
    assert loom.status == DocStatus.unknown
    assert loom.dependencies == ["doc_weaver_identity_card_pehchan"]

    # Check ranking
    assert len(plan.ranking) == 1
    assert plan.ranking[0].name == "Loom Inspection Certificate"
    assert plan.ranking[0].status == "unknown"


# ============================================================================
# 2. Example 5 Exact Scenario (Student)
# ============================================================================

def test_prompt_example_5_student_ranking():
    """
    Exact Example 5 from Prompt:
      Income Certificate (have, green)   -> Scholarship A, Fee Concession B
      Caste Certificate (missing, red)   -> Scholarship A
      Admission Proof (unknown, grey)    -> Scholarship A
      Priority list: 1. Caste Certificate (helps 1 application), then Admission Proof.
    """
    src = "https://example.gov.in/test"
    scheme_a = SchemeRecord(
        id="scholarship_a",
        name="Scholarship A",
        documents=[
            {"name": "Income Certificate", "source_url": src},
            {"name": "Caste Certificate", "source_url": src},
            {"name": "Admission Proof", "source_url": src},
        ],
        verification_status="verified",
    )
    scheme_b = SchemeRecord(
        id="fee_concession_b",
        name="Fee Concession B",
        documents=[
            {"name": "Income Certificate", "source_url": src},
        ],
        verification_status="verified",
    )

    user_docs = {
        "doc_income_certificate": "have",
        "doc_caste_certificate": "dont_have",
        # Admission Proof not answered -> unknown
    }

    plan = build_action_plan([scheme_a, scheme_b], user_documents=user_docs)

    # 1. Statuses
    doc_map = {c.id: c for c in plan.checklist}
    assert doc_map["doc_income_certificate"].status == DocStatus.have
    assert doc_map["doc_caste_certificate"].status == DocStatus.dont_have
    assert doc_map["doc_admission_proof"].status == DocStatus.unknown

    # 2. Priority Ranking: 1. Caste Certificate (helps 1 application), then Admission Proof
    assert len(plan.ranking) == 2
    assert plan.ranking[0].name == "Caste Certificate"
    assert plan.ranking[0].status == "dont_have"
    assert plan.ranking[0].helps_count == 1
    assert plan.ranking[0].summary == "Caste Certificate (helps 1 application)"

    assert plan.ranking[1].name == "Admission Proof"
    assert plan.ranking[1].status == "unknown"
    assert plan.ranking[1].helps_count == 1

    # 3. Mermaid Colors
    mermaid = render_mermaid(plan)
    assert 'doc_income_certificate["Income Certificate (have)"]:::have' in mermaid
    assert 'doc_caste_certificate["Caste Certificate (dont_have)"]:::dont_have' in mermaid
    assert 'doc_admission_proof["Admission Proof (unknown)"]:::unknown' in mermaid


def test_student_data_file_scenario(student_schemes):
    """Test using data/schemes/students.json file."""
    user_docs = {
        "doc_income_certificate": "have",
        "doc_caste_certificate": "dont_have",
        "doc_domicile_certificate": "have",
    }
    plan = build_action_plan(student_schemes, user_documents=user_docs)

    doc_map = {c.id: c for c in plan.checklist}
    assert doc_map["doc_income_certificate"].status == DocStatus.have
    assert doc_map["doc_caste_certificate"].status == DocStatus.dont_have
    assert doc_map["doc_admission_proof"].status == DocStatus.unknown

    # Domicile is already possessed, so Caste Certificate is unblocked and comes first among missing
    assert plan.ranking[0].doc_id == "doc_caste_certificate"
    assert plan.ranking[0].status == "dont_have"

    graph_dict = plan.to_graph_dict()
    assert "nodes" in graph_dict
    assert "edges" in graph_dict
    assert "ranking" in graph_dict


# ============================================================================
# 3. Farmer Scenario (Same code, different data)
# ============================================================================

def test_farmer_scenario_with_have_dont_have_unknown(farmer_schemes):
    """
    Example for a farmer from prompt:
      Land Record (RTC/Pahani): dont_have
      Aadhaar-linked Bank Account: have
      Crop Sowing Certificate: unknown
    """
    user_docs = {
        "doc_land_record_rtc": "dont_have",
        "doc_aadhaar_linked_bank_account": "have",
        # Crop Sowing Certificate omitted -> unknown
    }

    plan = build_action_plan(farmer_schemes, user_documents=user_docs)

    doc_map = {c.id: c for c in plan.checklist}
    assert doc_map["doc_land_record_rtc"].status == DocStatus.dont_have
    assert doc_map["doc_aadhaar_linked_bank_account"].status == DocStatus.have
    assert doc_map["doc_crop_sowing_certificate"].status == DocStatus.unknown

    # Land Record is needed before Crop Sowing Certificate, and helps multiple schemes
    rtc_item = doc_map["doc_land_record_rtc"]
    sowing_item = doc_map["doc_crop_sowing_certificate"]
    assert rtc_item.order < sowing_item.order

    # Ranking verifies missing documents priority order
    ranking = plan.ranking
    assert len(ranking) >= 2
    assert ranking[0].doc_id == "doc_land_record_rtc"
    assert ranking[0].status == "dont_have"
    assert ranking[0].helps_count >= 2


# ============================================================================
# 4. User Who Has All Documents
# ============================================================================

def test_user_has_all_documents(farmer_schemes):
    """When the user has all required documents, ranking is empty and all are green."""
    agent = Agent3()
    all_docs = agent.collect_required_documents(farmer_schemes)
    user_docs = {d["id"]: "have" for d in all_docs}

    plan = agent.build_plan(farmer_schemes, user_documents=user_docs)

    # All items have status have
    for item in plan.checklist:
        assert item.status == DocStatus.have

    # Missing documents ranking is empty
    assert len(plan.ranking) == 0

    # Mermaid contains :::have for all documents and no dont_have or unknown classes
    mermaid = agent.render_mermaid(plan)
    assert ":::have" in mermaid
    assert ":::dont_have" not in mermaid
    assert ":::unknown" not in mermaid


# ============================================================================
# 5. User Who Has None of the Documents
# ============================================================================

def test_user_has_no_documents(student_schemes):
    """When the user has no documents (all dont_have), all are ranked missing and red."""
    agent = Agent3()
    all_docs = agent.collect_required_documents(student_schemes)
    user_docs = {d["id"]: "dont_have" for d in all_docs}

    plan = agent.build_plan(student_schemes, user_documents=user_docs)

    # Every required document is in checklist as dont_have
    for item in plan.checklist:
        assert item.status == DocStatus.dont_have

    # Every document is included in the priority ranking
    assert len(plan.ranking) == len(plan.checklist)
    for r in plan.ranking:
        assert r.status == "dont_have"

    # Mermaid has :::dont_have for documents and no :::have
    mermaid = agent.render_mermaid(plan)
    assert ":::dont_have" in mermaid
    assert ":::have" not in mermaid


# ============================================================================
# 6. Midway Status Updates / Answers Change
# ============================================================================

def test_answers_change_midway_regenerates_graph(farmer_schemes):
    """Tests dynamic graph regeneration when a user changes an answer midway."""
    agent = Agent3()

    # Step 1: Initial state - Land Record missing, Crop Sowing unknown
    user_docs: dict[str, str] = {
        "doc_land_record_rtc": "dont_have",
        "doc_crop_sowing_certificate": "unknown",
        "doc_aadhaar_linked_bank_account": "have",
    }
    plan_initial = agent.build_plan(farmer_schemes, user_documents=user_docs)
    initial_ranking_ids = [r.doc_id for r in plan_initial.ranking]
    assert "doc_land_record_rtc" in initial_ranking_ids

    # Step 2: User obtains Land Record and answers "I have it"
    agent.record_document_status(user_docs, "doc_land_record_rtc", "have")
    plan_updated = agent.build_plan(farmer_schemes, user_documents=user_docs)

    updated_doc_map = {c.id: c for c in plan_updated.checklist}
    assert updated_doc_map["doc_land_record_rtc"].status == DocStatus.have

    # Land Record is now removed from missing ranking
    updated_ranking_ids = [r.doc_id for r in plan_updated.ranking]
    assert "doc_land_record_rtc" not in updated_ranking_ids
    assert "doc_crop_sowing_certificate" in updated_ranking_ids

    # In Mermaid, Land Record is now green (:::have)
    mermaid = agent.render_mermaid(plan_updated)
    assert 'doc_land_record_rtc["Land Record (RTC/Pahani) (have)"]:::have' in mermaid


# ============================================================================
# 7. Agent 3 Plain Language Questioning Flow
# ============================================================================

def test_agent3_plain_language_questions(student_schemes):
    agent = Agent3()
    # If user already answered Income Certificate as 'have'
    user_docs = {"doc_income_certificate": "have"}

    questions = agent.generate_document_questions(student_schemes, user_documents=user_docs)
    assert len(questions) > 0

    # Ensure Income Certificate is not asked again
    asked_ids = [q["doc_id"] for q in questions]
    assert "doc_income_certificate" not in asked_ids

    # Ensure question format is plain language
    for q in questions:
        assert q["question"].startswith("Do you have your ")
        assert q["question"].endswith("?")
        assert q["options"] == ["have", "dont_have", "unknown"]


# ============================================================================
# 8. Mermaid and Obsidian Notes Rendering
# ============================================================================

def test_render_mermaid_colors(student_schemes):
    plan = build_action_plan(
        student_schemes,
        user_documents={
            "doc_income_certificate": "have",
            "doc_caste_certificate": "dont_have",
        }
    )
    mermaid = render_mermaid(plan)
    assert "classDef have fill:#4CAF50" in mermaid
    assert "classDef dont_have fill:#F44336" in mermaid
    assert "classDef unknown fill:#9E9E9E" in mermaid
    assert "classDef scheme fill:#1976D2" in mermaid
    assert ":::have" in mermaid
    assert ":::dont_have" in mermaid
    assert ":::unknown" in mermaid


def test_render_obsidian_notes_in_scheme_map(student_schemes, tmp_path):
    plan = build_action_plan(
        student_schemes,
        user_documents={"doc_income_certificate": "have", "doc_caste_certificate": "dont_have"}
    )
    scheme_map_dir = tmp_path / "scheme-map"
    written = render_obsidian_notes(plan, output_dir=scheme_map_dir)

    assert len(written) > 0
    assert (scheme_map_dir / "README.md").is_file()
    assert (scheme_map_dir / "Overview.md").is_file()

    readme_text = (scheme_map_dir / "README.md").read_text(encoding="utf-8")
    assert "Unlocked: Schemes & Documents Dependency Map" in readme_text
    assert "[[Caste Certificate]]" in readme_text
    assert "```mermaid" in readme_text

    # Check scheme notes
    schemes_dir = scheme_map_dir / "schemes"
    assert schemes_dir.is_dir()
    scheme_files = list(schemes_dir.glob("*.md"))
    assert len(scheme_files) == len(student_schemes)
    first_scheme_text = scheme_files[0].read_text(encoding="utf-8")
    assert "[[" in first_scheme_text

    # Check document notes
    docs_dir = scheme_map_dir / "documents"
    assert docs_dir.is_dir()
    doc_files = list(docs_dir.glob("*.md"))
    assert len(doc_files) >= 3
    income_file = next(f for f in doc_files if "income_certificate" in f.name)
    income_text = income_file.read_text(encoding="utf-8")
    assert "have" in income_text
    assert "Issuing Authority:" in income_text
