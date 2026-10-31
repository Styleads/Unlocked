from member2.attributes import ATTRIBUTES, INCOME_RANGES, is_canonical, resolve_attribute
from member2.documents import DOCUMENTS, normalize_document_name, resolve_document
from member2.models import InputType

SPEC_ATTRIBUTES = {
    "state", "district", "age", "gender", "education_level", "course_type",
    "year_of_study", "institution_type", "annual_family_income", "social_category",
    "is_minority", "has_disability", "employment_status",
    "previous_year_marks_percent", "domicile_karnataka", "receives_other_scholarship",
}


def test_all_spec_attributes_present():
    assert SPEC_ATTRIBUTES <= set(ATTRIBUTES)


def test_every_attribute_is_askable():
    for spec in ATTRIBUTES.values():
        assert spec.question.endswith("?")
        assert spec.why_template
        if spec.input_type == InputType.select:
            assert spec.options
        if spec.input_type == InputType.range:
            assert spec.ranges


def test_no_not_sure_select_option():
    # "Not sure" is an answer state, never a value (DECISIONS.md #8).
    for spec in ATTRIBUTES.values():
        assert all("not sure" not in o.lower() for o in spec.options)


def test_income_ranges_inclusive_and_non_overlapping():
    for prev, nxt in zip(INCOME_RANGES, INCOME_RANGES[1:]):
        assert prev.max is not None and nxt.min == prev.max + 1
    assert INCOME_RANGES[0].min == 0 and INCOME_RANGES[-1].max is None


def test_resolve_attribute_aliases():
    assert resolve_attribute("Family Income") == "annual_family_income"
    assert resolve_attribute("parental income") == "annual_family_income"
    assert resolve_attribute("annual_family_income") == "annual_family_income"
    assert resolve_attribute("Caste") == "social_category"
    assert resolve_attribute("Category") == "social_category"
    assert resolve_attribute("hostel resident") is None


def test_is_canonical():
    assert is_canonical("age")
    assert not is_canonical("unmapped:hostel")
    assert not is_canonical(None)


def test_document_aliases_merge():
    assert {resolve_document(n) for n in ("Income Certificate", "income cert.", "Family income certificate")} == {
        "doc_income_certificate"
    }
    assert normalize_document_name("income cert.") == ("doc_income_certificate", "Income Certificate")


def test_unknown_document_gets_own_id():
    assert normalize_document_name("Hostel Warden Letter!") == ("doc_hostel_warden_letter", "Hostel Warden Letter")
    assert all(d.startswith("doc_") for d in DOCUMENTS)
