"""Help after a rejection. The user's notice is redacted before the LLM sees it.
A next step is kept only if its evidence is a verbatim quote from official
guidance we were given (with its source URL); otherwise we say we couldn't find
an official route, and never suggest an appeal on our own."""
from __future__ import annotations

from typing import Any, Iterable, Optional

from .grounding import call_llm_json, contains_verbatim, redact, unsupported_numbers
from .models import (
    EmailPurpose,
    EmailRequest,
    NextStep,
    RejectionAnalysis,
    RejectionRoute,
    SchemeContext,
    SourcedFact,
)

SYSTEM = (
    "You help a citizen in Karnataka, India understand a rejected welfare-scheme application. "
    "You get the rejection notice and numbered official guidance passages. "
    "1) reason_quote: copy the exact sentence from the notice that states the reason, or null. "
    "2) reason_summary: one plain sentence explaining it, or null. "
    "3) next_steps: only routes that a guidance passage explicitly provides (correction, reapplication, "
    "appeal, clarification). For each give route, a one-sentence description, evidence (an exact quote "
    "from that passage), source_index (the passage number) and deadline_text (an exact quote of any time "
    "limit, or null). If no passage provides a route, return an empty list. Never invent a route, office, "
    "deadline or contact. "
    'Return only JSON: {"reason_quote": ..., "reason_summary": ..., "next_steps": [...]}'
)

ROUTE_PURPOSE = {
    RejectionRoute.correction: EmailPurpose.correction_request,
    RejectionRoute.reapplication: EmailPurpose.inquiry,
    RejectionRoute.appeal: EmailPurpose.appeal,
    RejectionRoute.clarification: EmailPurpose.clarification,
}

NO_ROUTE = (
    "We couldn't find an officially stated next step (such as a correction, reapplication or appeal) "
    "in the sources we have. You can ask the department directly; we can draft a clarification email for you."
)


def _step(item: Any, guidance: list[SourcedFact]) -> Optional[NextStep]:
    if not isinstance(item, dict):
        return None
    try:
        route = RejectionRoute(str(item.get("route", "")).strip().lower())
        idx = int(item.get("source_index"))
    except (ValueError, TypeError):
        return None
    if not 0 <= idx < len(guidance):
        return None
    passage = guidance[idx]
    evidence, desc = item.get("evidence"), item.get("description")
    if not isinstance(evidence, str) or not contains_verbatim(passage.text, evidence):
        return None
    if not isinstance(desc, str) or not 5 <= len(desc) <= 400 or unsupported_numbers(desc, [passage.text]):
        return None
    deadline = item.get("deadline_text")
    if not (isinstance(deadline, str) and contains_verbatim(passage.text, deadline)):
        deadline = None
    return NextStep(route=route, description=desc.strip(), evidence=evidence.strip(),
                    source_url=passage.source_url, deadline_text=deadline)


def analyse_rejection(
    scheme: SchemeContext | dict,
    notice_text: str,
    guidance: Iterable[SourcedFact | dict] = (),
    *,
    llm: Optional[Any] = None,
    simulated: bool = False,
) -> RejectionAnalysis:
    s = scheme if isinstance(scheme, SchemeContext) else SchemeContext.model_validate(scheme)
    passages = [g if isinstance(g, SourcedFact) else SourcedFact.model_validate(g) for g in guidance]
    passages = [p for p in passages if p.text.strip() and p.source_url]
    notice = redact(notice_text or "")
    warnings: list[str] = []
    if simulated:
        warnings.append("This is a simulated rejection for the demo.")

    base = dict(scheme_id=s.id, simulated=simulated)
    if not notice.strip():
        return RejectionAnalysis(**base, explanation="Paste the text of your rejection notice so we can look at it.", warnings=warnings)
    if llm is None:
        return RejectionAnalysis(**base, explanation="Automatic reading of the notice isn't available right now. " + NO_ROUTE, warnings=warnings)

    data = call_llm_json(
        llm, SYSTEM,
        {"scheme_name": s.name, "notice": notice,
         "guidance": [{"index": i, "text": p.text} for i, p in enumerate(passages)]},
        task="rejection_assist", ref=s.id,
    )
    if data is None:
        return RejectionAnalysis(**base, explanation="We couldn't read the notice automatically. " + NO_ROUTE, warnings=warnings)

    quote = data.get("reason_quote")
    if not (isinstance(quote, str) and contains_verbatim(notice, quote)):
        if quote:
            warnings.append("The stated reason couldn't be matched to your notice, so it isn't shown.")
        quote = None
    summary = data.get("reason_summary")
    if not (isinstance(summary, str) and 5 <= len(summary) <= 400 and not unsupported_numbers(summary, [notice])) or quote is None:
        summary = None  # a summary is only shown alongside the verified quote it explains

    raw_steps = data.get("next_steps") if isinstance(data.get("next_steps"), list) else []
    steps = [st for st in (_step(i, passages) for i in raw_steps) if st is not None]
    if len(steps) < len(raw_steps):
        warnings.append(f"{len(raw_steps) - len(steps)} suggested step(s) couldn't be matched to official guidance and were left out.")
    # One step per route and source keeps the list short and stable.
    seen, unique = set(), []
    for st in steps:
        if (st.route, st.source_url) not in seen:
            seen.add((st.route, st.source_url))
            unique.append(st)

    if unique:
        explanation = "Based on the official guidance, these next steps are available. Check each source before acting."
    else:
        explanation = NO_ROUTE
    return RejectionAnalysis(**base, reason_quote=quote, reason_summary=summary, next_steps=unique,
                             supported=bool(unique), explanation=explanation, warnings=warnings, analysed_by="llm")


def email_request_for_step(
    scheme: SchemeContext | dict, step: Optional[NextStep], question: str, user_details: Optional[dict[str, str]] = None,
) -> EmailRequest:
    """An email request for a sourced next step, or a clarification email when
    there is no supported route. The step's evidence travels as a sourced fact."""
    s = scheme if isinstance(scheme, SchemeContext) else SchemeContext.model_validate(scheme)
    if step is None:
        return EmailRequest(scheme=s, purpose=EmailPurpose.clarification, question=question, user_details=user_details or {})
    return EmailRequest(scheme=s, purpose=ROUTE_PURPOSE[step.route], question=question, user_details=user_details or {},
                        facts=[SourcedFact(text=step.evidence, source_url=step.source_url)])
