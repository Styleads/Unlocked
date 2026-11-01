"""Unit tests for Phase 2: Office enrichment in Discovery Agent."""
import pytest
from discovery_agent.fallback_schemes import get_fallback_schemes
from discovery_agent.adapter import to_canonical_scheme
from api.orchestrator import build_scheme_views


def test_fallback_schemes_contain_office_contact():
    schemes = get_fallback_schemes()
    assert len(schemes) >= 5

    # Check SSP Post-Matric SC/ST scheme
    ssp = next(s for s in schemes if s.id == "fallback-ssp-scst-001")
    assert ssp.office_name == "Social Welfare Department Helpline & e-Attestation Cell"
    assert "M.S. Building" in ssp.office_address
    assert ssp.whatsapp_number == "+918277712345"
    assert ssp.contact_email == "postmatrichelp@karnataka.gov.in"
    assert ssp.reception_number == "080-22634300"
    assert ssp.contact_source == "website"

    # Check office hours structure
    assert isinstance(ssp.office_hours, dict)
    assert "monday" in ssp.office_hours
    assert ssp.office_hours["monday"]["open"] == "10:00"
    assert ssp.office_hours["monday"]["close"] == "17:30"
    assert ssp.office_hours["timezone"] == "Asia/Kolkata"

    # Check unified office_contact dictionary
    assert isinstance(ssp.office_contact, dict)
    assert ssp.office_contact["office_name"] == ssp.office_name
    assert ssp.office_contact["verification_status"] == "verified"


def test_adapter_maps_custom_office_contact():
    raw_data = {
        "id": "test-custom-scheme-001",
        "name": "Karnataka Farmer Water Subsidy",
        "official_sources": ["https://raitamitra.karnataka.gov.in"],
        "office_contact": {
            "office_name": "District Agriculture Office",
            "office_address": "Mandya, Karnataka",
            "office_hours": {
                "monday": {"open": "10:00", "close": "17:00"},
                "timezone": "Asia/Kolkata"
            },
            "whatsapp_number": "+919876543210",
            "email": "mandya.agri@karnataka.gov.in",
            "reception_number": "08232-220000",
            "contact_source": "website",
            "verification_status": "verified",
        }
    }

    record = to_canonical_scheme(raw_data)
    assert record.office_name == "District Agriculture Office"
    assert record.office_address == "Mandya, Karnataka"
    assert record.whatsapp_number == "+919876543210"
    assert record.contact_email == "mandya.agri@karnataka.gov.in"
    assert record.reception_number == "08232-220000"
    assert record.office_contact["verification_status"] == "verified"


def test_scheme_view_exposes_office_contact():
    schemes = get_fallback_schemes()
    views = build_scheme_views(schemes=schemes, assessments=[])
    assert len(views) == len(schemes)

    ssp_view = next(v for v in views if v.id == "fallback-ssp-scst-001")
    assert ssp_view.office_name == "Social Welfare Department Helpline & e-Attestation Cell"
    assert ssp_view.whatsapp_number == "+918277712345"
    assert ssp_view.reception_number == "080-22634300"
    assert ssp_view.office_contact is not None
    assert ssp_view.office_contact["office_address"] == ssp_view.office_address
