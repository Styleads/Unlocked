"""Walk through the demo journey on the fictional test schemes and print what
happens at each step. Run from the repo root:  python -m member2.demo"""
from __future__ import annotations

import json
from pathlib import Path

from . import (
    apply_answers,
    assess_schemes,
    build_action_plan,
    generate_consolidated_questions,
    normalize_requirements,
    reassess_schemes,
)
from .models import SchemeRecord

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "member2" / "fixtures" / "schemes.json"


def heading(text: str) -> None:
    print(f"\n{'=' * 70}\n{text}\n{'=' * 70}")


def show_assessments(assessments, names) -> None:
    for a in assessments:
        print(f"\n  {names[a.scheme_id]}: {a.status.value.upper()}")
        print(f"    {a.explanation}")
        for r in a.requirements:
            print(f"      - [{r.status.value}] {r.criterion}  ->  {r.reason}")


def main() -> None:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    print(f"Note: {data['_note']}")
    schemes = normalize_requirements([SchemeRecord.model_validate(s) for s in data["schemes"]])
    names = {s.id: s.name for s in schemes}

    heading("STEP 1. Nothing answered yet")
    show_assessments(assess_schemes(schemes, {}), names)

    heading("STEP 2. Consolidated questions (asked once across all schemes)")
    for i, q in enumerate(generate_consolidated_questions(schemes, {}, {}), 1):
        used_by = ", ".join(names[s] for s in q.related_scheme_ids)
        print(f"  {i}. {q.question}\n     why: {q.why_asked}\n     used by: {used_by}")

    heading("STEP 3. User answers three questions and SKIPS institution type")
    submitted = [
        {"attribute": "annual_family_income", "state": "answered", "value": "₹1 lakh – ₹2.5 lakh"},
        {"attribute": "domicile_karnataka", "state": "answered", "value": "Yes"},
        {"attribute": "education_level", "state": "answered", "value": "undergraduate"},
        {"attribute": "institution_type", "state": "skipped"},
    ]
    answers, history = apply_answers({}, {}, submitted)
    for a in answers.values():
        print(f"  {a.attribute}: state={a.state.value}, stored value={a.value}")

    heading("STEP 4. Reassessment (the skipped answer stays UNKNOWN, not 'no')")
    after = reassess_schemes(schemes, answers)
    show_assessments(after, names)

    heading("STEP 5. Next question batch (nothing repeated)")
    nxt = generate_consolidated_questions(schemes, answers, history)
    print("  " + ("\n  ".join(q.question for q in nxt) if nxt else "(none)"))

    heading("STEP 6. Document plan for Demo Scholarship A + Demo Fee Concession B")
    by_id = {s.id: s for s in schemes}
    plan = build_action_plan([by_id["demo_scholarship_a"], by_id["demo_fee_concession_b"]], assessments=after)
    print(f"  {plan.explanation}\n")
    for c in plan.checklist:
        print(f"  {c.order}. {c.name}  [{c.status.value}]\n     {c.reason}")
    print(f"\n  Shared prerequisites: {plan.shared_prerequisites}")
    print(f"  Graph edges (each has a source): {len(plan.edges)}")
    for w in plan.warnings:
        print(f"  WARNING: {w}")

    heading("STEP 7. What if the user had answered marks = 40 for Demo Merit Award C?")
    bad, _ = apply_answers(answers, history, [{"attribute": "previous_year_marks_percent", "state": "answered", "value": 40}])
    show_assessments([a for a in assess_schemes(schemes, bad) if a.scheme_id == "demo_merit_c"], names)


if __name__ == "__main__":
    main()
