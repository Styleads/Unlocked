import pytest

from member2.comparators import evaluate
from member2.models import Answer, AnswerState, Operator, RequirementStatus as S

NON_ANSWERED = [s for s in AnswerState if s != AnswerState.answered]


def ans(value):
    return Answer(attribute="x", state=AnswerState.answered, value=value)


def status(op, required, value):
    return evaluate(op, required, ans(value))[0]


# --- the invariant: missing information is never a failure -------------------

@pytest.mark.parametrize("op", list(Operator))
@pytest.mark.parametrize("state", NON_ANSWERED)
def test_non_answered_is_always_unknown(op, state):
    result, reason = evaluate(op, 250000, Answer(attribute="x", state=state, value=1))
    assert result == S.unknown and reason


@pytest.mark.parametrize("op", list(Operator))
def test_missing_answer_is_unknown(op):
    assert evaluate(op, 1, None)[0] == S.unknown


@pytest.mark.parametrize("text", ["Not sure", " not sure ", "Don't know", "unknown"])
def test_not_sure_text_value_is_unknown(text):
    assert status(Operator.in_, ["Government", "Aided"], text) == S.unknown


def test_answered_none_value_is_unknown():
    assert status(Operator.lte, 10, None) == S.unknown


# --- numeric scalars ---------------------------------------------------------

@pytest.mark.parametrize(
    "op,required,value,expected",
    [
        (Operator.lte, 250000, 200000, S.satisfied),
        (Operator.lte, 250000, 250000, S.satisfied),
        (Operator.lte, 250000, 250001, S.not_satisfied),
        (Operator.lt, 18, 17, S.satisfied),
        (Operator.lt, 18, 18, S.not_satisfied),
        (Operator.gte, 60, 60, S.satisfied),
        (Operator.gte, 60, 59.5, S.not_satisfied),
        (Operator.gt, 60, 61, S.satisfied),
        (Operator.gt, 60, 60, S.not_satisfied),
        (Operator.gte, "60", "75", S.satisfied),
        (Operator.lte, "2,50,000", "1,00,000", S.satisfied),
    ],
)
def test_numeric_scalar(op, required, value, expected):
    assert status(op, required, value) == expected


# --- numeric ranges (interval logic, both ends inclusive) ---------------------

@pytest.mark.parametrize(
    "op,required,value,expected",
    [
        (Operator.lte, 250000, {"min": 100000, "max": 200000}, S.satisfied),
        (Operator.lte, 250000, {"min": 100000, "max": 250000}, S.satisfied),
        (Operator.lte, 250000, {"min": 250001, "max": 500000}, S.not_satisfied),
        (Operator.lte, 250000, {"min": 200000, "max": 300000}, S.unknown),
        # open side that doesn't matter: still decidable
        (Operator.lte, 250000, {"min": 800001, "max": None}, S.not_satisfied),
        (Operator.lte, 250000, {"min": None, "max": 99999}, S.satisfied),
        # open side that does matter: undecidable
        (Operator.lte, 250000, {"min": 100000, "max": None}, S.unknown),
        (Operator.gte, 60, {"min": 70, "max": None}, S.satisfied),
        (Operator.gte, 60, {"min": None, "max": 50}, S.not_satisfied),
        (Operator.lt, 250000, {"min": 100000, "max": 250000}, S.unknown),
        (Operator.gt, 60, {"min": 50, "max": 60}, S.not_satisfied),
        (Operator.lte, 250000, {"min": None, "max": None}, S.unknown),
    ],
)
def test_numeric_range(op, required, value, expected):
    assert status(op, required, value) == expected


def test_straddle_reason_mentions_overlap():
    _, reason = evaluate(Operator.lte, 250000, ans({"min": 200000, "max": 300000}))
    assert "overlaps the limit (at most 2,50,000)" in reason


@pytest.mark.parametrize(
    "limit,shown",
    [(60, "at least 60"), (1000, "at least 1,000"), (250000, "at least 2,50,000"), (12500000, "at least 1,25,00,000"), (62.5, "at least 62.5")],
)
def test_limits_use_indian_grouping(limit, shown):
    assert shown in evaluate(Operator.gte, limit, ans(limit))[1]


@pytest.mark.parametrize(
    "required,value",
    [
        (250000, "about two lakh"),
        ("a lot", 100),
        (250000, True),  # bools are not numbers
        (250000, {"min": 300000, "max": 100000}),  # inverted range
        (250000, {"min": "abc", "max": 5}),
        (250000, [1, 2]),
    ],
)
def test_numeric_bad_types_need_clarification(required, value):
    assert status(Operator.lte, required, value) == S.needs_clarification


# --- equality ----------------------------------------------------------------

@pytest.mark.parametrize(
    "op,required,value,expected",
    [
        (Operator.eq, "Karnataka", " karnataka ", S.satisfied),
        (Operator.eq, "Karnataka", "Kerala", S.not_satisfied),
        (Operator.neq, "Private", "Government", S.satisfied),
        (Operator.neq, "Private", "PRIVATE", S.not_satisfied),
        (Operator.eq, 2, "2.0", S.satisfied),
        (Operator.eq, True, "true", S.satisfied),
    ],
)
def test_equality(op, required, value, expected):
    assert status(op, required, value) == expected


def test_equality_with_range_needs_clarification():
    assert status(Operator.eq, 5, {"min": 1, "max": 9}) == S.needs_clarification


# --- membership --------------------------------------------------------------

@pytest.mark.parametrize(
    "op,required,value,expected",
    [
        (Operator.in_, ["Undergraduate", "Diploma"], "undergraduate", S.satisfied),
        (Operator.in_, ["Undergraduate", "Diploma"], "Postgraduate", S.not_satisfied),
        (Operator.not_in, ["Private"], "Aided", S.satisfied),
        (Operator.not_in, ["Private"], " private", S.not_satisfied),
        (Operator.in_, [1, 2], "2", S.satisfied),
    ],
)
def test_membership(op, required, value, expected):
    assert status(op, required, value) == expected


@pytest.mark.parametrize("required", ["Government", [], 5])
def test_membership_needs_list(required):
    assert status(Operator.in_, required, "Government") == S.needs_clarification


# --- booleans ----------------------------------------------------------------

@pytest.mark.parametrize(
    "op,value,expected",
    [
        (Operator.is_true, True, S.satisfied),
        (Operator.is_true, "Yes", S.satisfied),
        (Operator.is_true, False, S.not_satisfied),
        (Operator.is_true, "no", S.not_satisfied),
        (Operator.is_false, "false", S.satisfied),
        (Operator.is_false, True, S.not_satisfied),
    ],
)
def test_boolean(op, value, expected):
    assert evaluate(op, None, ans(value))[0] == expected


@pytest.mark.parametrize("value", ["maybe", 1, {"min": 0}])
def test_boolean_bad_types_need_clarification(value):
    assert evaluate(Operator.is_true, None, ans(value))[0] == S.needs_clarification


# --- unreadable rules --------------------------------------------------------

def test_missing_operator_needs_clarification():
    assert status(None, 5, 5) == S.needs_clarification


@pytest.mark.parametrize("op", [Operator.lte, Operator.eq, Operator.in_])
def test_missing_required_value_needs_clarification(op):
    assert status(op, None, 5) == S.needs_clarification
