"""Unit tests for Phase 2: Office enrichment in Discovery Agent."""
import pytest
from discovery_agent.fallback_schemes import get_fallback_schemes
from discovery_agent.adapter import to_canonical_scheme
from api.orchestrator import build_scheme_views


def test_fallback_schemes_carry_no_invented_office_contact():
    schemes = get_fallback_schemes()
    assert len(schemes) >= 5

    for s in schemes:
        if not s.office_contact:
            continue
        # A made-up phone, WhatsApp number, email, address or set of hours would look official: none is shipped.
        assert not s.whatsapp_number and not s.reception_number and not s.contact_email
        assert not s.office_address and not s.office_hours
        assert s.office_contact["contact_source"] == "simulated"
        assert s.office_contact["verification_status"] == "unverified"

    ssp = next(s for s in schemes if s.id == "fallback-ssp-scst-001")
    assert ssp.office_name  # a descriptive desk label remains for the simulation


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


def test_scheme_view_exposes_office_contact_as_unverified():
    schemes = get_fallback_schemes()
    views = build_scheme_views(schemes=schemes, assessments=[])
    assert len(views) == len(schemes)

    ssp_view = next(v for v in views if v.id == "fallback-ssp-scst-001")
    assert ssp_view.office_name
    assert ssp_view.whatsapp_number is None and ssp_view.reception_number is None
    assert ssp_view.office_contact is not None
    assert ssp_view.office_contact["verification_status"] == "unverified"


def test_a_contact_without_a_verification_flag_is_unverified():
    record = to_canonical_scheme({
        "id": "no-flag", "name": "Demo Scheme", "official_sources": ["https://example.gov.in/x"],
        "office_contact": {"office_name": "Demo Desk", "whatsapp_number": "+919876543210"},
    })
    assert record.office_contact["verification_status"] == "unverified"
