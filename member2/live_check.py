"""Try the real LLM path once on a fictional scheme. Run from the repo root:
    $env:GEMINI_API_KEY="..."; python -m member2.live_check
Prints rule statuses and question wording only, never answer values."""
from __future__ import annotations

from . import LLMError, default_client, generate_consolidated_questions, normalize_requirements
from .models import SchemeRecord

TEXT = (
    "Demo Scholarship Z is open to undergraduate students whose annual family income "
    "is below Rs 2.5 lakh and who are domiciled in Karnataka. Applicants must have "
    "scored at least 60% in the previous year."
)


_SKIP = ("tts", "image", "lyria", "transcribe", "antigravity", "research", "robotics", "computer-use", "omni", "nano", "gemma", "customtools")


def _find_working_model(llm):
    """Try other text models on the key until one answers."""
    try:
        names = [m for m in llm.list_models() if "flash" in m and not any(k in m for k in _SKIP)]
    except LLMError as exc:
        print(f"  {exc}")
        return None
    print("Trying other models...")
    for name in names[:8]:
        if name == llm.model:
            continue
        candidate = type(llm)(model=name)
        try:
            candidate.complete_json("Reply with a JSON object.", 'Return {"ok": true}')
        except LLMError as exc:
            print(f"  {name}: {exc}")
            continue
        print(f"  {name}: OK  -> set $env:UNLOCKED_MODEL=\"{name}\" to keep using it")
        return candidate
    print("No model answered. Try again in a few minutes.")
    return None


def main() -> None:
    llm = default_client()
    print(f"Client: {type(llm).__name__}, model: {llm.model}")
    # The normalizer swallows LLM errors by design, so probe once to show the real reason.
    try:
        llm.complete_json("Reply with a JSON object.", 'Return {"ok": true}')
        resolved = getattr(llm, "resolved_model", None)
        print(f"Probe call: OK" + (f" (model actually used: {resolved})" if resolved else ""))
    except LLMError as exc:
        print(f"Probe call FAILED: {exc}")
        if not hasattr(llm, "list_models"):
            return
        llm = _find_working_model(llm)
        if llm is None:
            return
    scheme = SchemeRecord.model_validate({
        "id": "demo_live_z", "name": "Demo Scholarship Z",
        "eligibility_text": TEXT, "official_sources": ["https://example.gov.in/z"],
    })
    (done,) = normalize_requirements([scheme], llm)
    print("\nExtracted rules:")
    for r in done.requirements:
        print(f"  [{r.status.value}] {r.attribute} {r.operator.value if r.operator else None} {r.value}  <- {r.criterion!r}")
    for u in getattr(done, "uncertainties", []) or []:
        print(f"  uncertainty: {u}")
    print("\nQuestions (rephrased):")
    for q in generate_consolidated_questions([done], {}, {}, rephrase_llm=llm):
        print(f"  {q.question}")


if __name__ == "__main__":
    main()
