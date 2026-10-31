# Member 2 — Decisions

`plan.md` is the shared source of truth. `member2.md` is the build spec; where they conflict, `plan.md` wins and the choice is recorded here.

## Contract (plan.md wins)

1. **Requirement verification value** is `verified | unverified | uncertain` (plan §5.1 example uses `"unverified"`). Scheme-level `verification_status` keeps `verified | not_verified | uncertain`. A validator converts `not_verified` on a requirement to `unverified`.
2. **Checklist dependency field** is `dependencies` (plan §5.4), not `depends_on`.
3. **Question ids** are `"q_" + attribute` (e.g. `q_annual_family_income`). The plan's `q_annual_income` example is illustrative; ids are opaque to other members.
4. **Function names and argument names** follow plan §4E (`user_answers`, not `answers`). "Requirements" / "verified_requirements" arguments are the normalized `SchemeRecord`s, which carry them. Where plan and spec agree on position (e.g. `assess_schemes(schemes, user_answers)`) arguments stay positional; any parameter where they disagree, or that the plan doesn't have, is keyword-only.
5. **`reassess_schemes`** is exported as an alias of `assess_schemes` so the plan's "reassessment" deliverable is explicit.
6. **`SchemeRecord` and `Requirement` use `extra="allow"`** so fields added by Members 1/3 survive a dump and save.
7. **`benefit` is `Any`**; Member 2 never reads it.

## Spec fixes

8. **"Not sure" is not a select option.** Any such submitted value becomes answer state `unknown`.
9. **Ranges use interval logic, both ends inclusive.** An open side only blocks a verdict when it is the side that matters. A range that straddles the limit is `unknown` ("your range overlaps the limit"), so the scheme shows *More information needed* and the attribute is listed in `missing_attributes`.
10. **LLM-extracted requirements** are `verified` only if every extracted number also appears in the verbatim evidence; otherwise `uncertain`.
11. **Normalization is idempotent**: requirements are deduplicated by criterion text. The normalizer also fills attribute/operator/value for requirements Member 1 delivers with only `criterion` + evidence.
12. **Questions:** attributes needed only by unverified requirements, or only by schemes already *Unlikely to match*, are excluded from consolidated batches. `state` and `domicile_karnataka` are separate facts (residence vs legal domicile).
13. **Planning:** a document reachable only as a sourced dependency is still a node (empty `required_by_scheme_ids`). Order key includes document status (`needed` before `have`/`obtained`). Edge direction: document → scheme (`required_for`), prerequisite → dependent (`prerequisite_of`).
14. **Contradictions:** two requirements on the same attribute in one scheme with conflicting values become `needs_clarification` with a warning (plan §4A).
15. **Plain-string documents** from Member 1 are coerced to unsourced `DocumentRequirement`s, then excluded from the plan with a visible warning.

## Phase 1 additions

18. **`Answer` drops `value` unless `state == answered`**, enforced in the model, so a skipped answer can never be compared.
19. **`AttributeSpec.ranges`** (label + inclusive `min`/`max`) added for range attributes so the frontend can show income bands and submit `{min, max}`. Bands do not share a boundary (₹2,50,000 then ₹2,50,001).
20. **Two attributes beyond the spec table:** `residence_area` and `household_card_type` (BPL/APL), common in Karnataka criteria. Remove if the real demo schemes never use them.
21. **Documents split per spec:** Admission Proof and Fee Receipt are separate items. Added Ration Card and Transfer Certificate.

## Phase 2 additions

22. **"Not sure" typed as an answered value** ("not sure", "don't know", "unknown", …) evaluates to `unknown`, as a second guard behind the conversion in `apply_answers`.
23. **Booleans are never numbers** (`True` does not compare as 1); numeric strings with Indian digit grouping ("2,50,000") are accepted.
24. **Range answer with both sides open** is `unknown`, not `needs_clarification`: the user gave no usable information.
25. Reasons mention the scheme's threshold, never the user's own value, so they are safe to show and to log.

## Phase 3 additions

26. **Any non-canonical attribute** (not only `None` / `unmapped:*`) gives `needs_clarification`, as a guard if a requirement skips normalization.
27. **Contradiction rule:** verified requirements on the same attribute *and* operator with different values are all `needs_clarification` ("The sources state different values"). A `gte` and an `lte` on one attribute is a range, not a conflict.
28. **Unverified rule reasons** mention a possible conflict ("Your answer may not meet it, once it is confirmed") without ever producing `not_satisfied`.
29. **Inputs are forgiving:** schemes may be `SchemeRecord` or dict; answers may be a dict keyed by attribute or a list, of `Answer` or dict. Inputs are never mutated.
30. **Optional keyword-only `now`** on `assess_scheme(s)` makes timestamps testable; all assessments in one call share one timestamp.

## Phase 5 additions

31. **A question is only generated if its answer could change an assessment.** Counted requirements must be verified, mapped, have an operator, not be contradictory, and belong to a scheme not already *Unlikely to match*. So `n_verified_reqs` in the spec's score is simply the count of these, and `required_for_assessment` is always true for generated questions. The same rule applies to scheme-specific questions, so "Check my eligibility" on an *Unlikely* scheme returns no questions.
32. **`Question.ranges`** (moved `RangeOption` into `models.py`) carries income bands; boolean questions get `options = ["Yes", "No"]`. `why_asked` = attribute's reason + "Used by N of the schemes we found." (+ "You can skip this." if high sensitivity).
33. **`apply_answers` cleans values** to the attribute's shape: select values are matched case-insensitively to a registry option; a range band label becomes `{min, max}`; yes/no becomes a bool; numbers are parsed. Empty becomes `skipped`; "not sure" text or any value that can't be cleaned becomes `unknown` (never guessed, never a failure).
34. **Scheme-specific questions** return a re-askable question with its earlier state in `status` (e.g. `skipped`) when `include_skipped=True`, so the UI can say "you skipped this earlier".
35. **Rephrasing** is one LLM call per batch that receives only `{question_id: text}`, never answers. A rewrite is accepted only if it is a 5–200 character string ending in "?"; anything else keeps the registry text.

## Phase 4 additions

36. **No `temperature`** in `AnthropicClient` (spec said 0): current Claude models reject non-default sampling parameters with a 400. Determinism comes from validation, not sampling.
37. **`max_tokens` 8000, `effort: "low"`** (spec said 1500): models think adaptively, and a low cap risks truncated JSON. Truncation (`stop_reason == "max_tokens"`), refusals and empty output raise `LLMError`, which the normalizer treats like any other failure.
38. **Server-side refusal fallback** (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) is enabled for models that support it, so a misfired safety decline on scheme text still gets an answer. Other models via `UNLOCKED_MODEL` are called without it.
39. **One LLM call per scheme** does both jobs: structure Member 1's text-only requirements (`criteria_to_structure`) and extract rules from `eligibility_text`. Only scheme text is sent.
40. **The number check applies to both jobs.** A structured or extracted rule keeps/gets `verified` only if every number in its value appears in the evidence ("2.5 lakh" and "2,50,000" both count as 250000); otherwise `uncertain`.
41. **Model output is mapped onto the registry**, not trusted: unknown attributes become `unmapped:<slug>` (the model's own name if it gave one), operators not valid for the attribute's input type and select values that aren't registry options become `operator: None` → `needs_clarification`. Select values are recased to the registry option.
42. **If the extracted `criterion` isn't verbatim in the text, the verified `evidence` replaces it.**
43. **Idempotency marker:** LLM-touched requirements carry an extra field `normalized_by` (`structured` | `extracted`), which survives Member 3's JSON round trip. A scheme with extracted rules isn't re-extracted; structured rules aren't re-sent; repeated failures don't duplicate the uncertainty.
44. **`Requirement.id` defaults to `""`**, filled as `<scheme_id>_req_<n>` without colliding with existing ids.

## Phase 6 additions

45. **`build_action_plan(selected_schemes, *, user_documents=None, assessments=None)`.** plan.md's `verified_requirements` argument is dropped (the schemes carry their documents); everything after the first argument is keyword-only, so a positional call written from the plan's sketch fails loudly instead of being misread.
46. **Schemes are sorted by id first**, so the plan doesn't depend on the order Member 3 passes them in.
47. **A document the user already has (`have`/`obtained`) doesn't block the order**: its outgoing edges are ignored by the sort (but kept in `edges` and each item's `dependencies`). Done documents go last.
48. **Order key:** (done?, −schemes reachable, earliest verified deadline, doc id). A deadline counts only with `deadline_source_url`.
49. **Unsourced dependencies** are skipped with a warning but are not listed in `excluded_documents` (that list is for documents dropped entirely). Self-dependencies are ignored with a warning; cycles are broken by removing the cycle's document→document edges, with a warning.
50. **When the same edge appears twice**, the first source URL (in scheme-id order) is kept on the edge; every source URL still appears in the item's `source_urls`.
51. **`nodes`** lists documents in plan order, then schemes by id; `edges` are sorted by (source, target).

## Wording polish

52. User-facing text: no doubled punctuation after quoted rules; singular/plural ("This rule hasn't…"); "Your answer about <detail> doesn't appear to meet this rule"; attribute labels lowercase only their first letter (so "Karnataka" keeps its capital; `domicile_karnataka` is labelled "Domicile in Karnataka"); "One of the schemes we found uses this." / "N of the schemes we found use this."; thresholds in reasons use Indian digit grouping (2,50,000).

## LLM provider

53. **Gemini added as a free-tier alternative** (`GeminiClient`, default `gemini-flash-lite-latest`: `gemini-2.5-flash` returned 404 and `gemini-flash-latest` 503 on the free tier; aliases avoid retired names), stdlib-only REST so there is no new dependency. Key is sent in a header, never the URL. Failures, blocks and truncation raise `LLMError`, same as Claude. 429/5xx are retried 4 times with backoff. `default_client()` uses Gemini if `GEMINI_API_KEY`/`GOOGLE_API_KEY` is set, else Claude. `UNLOCKED_MODEL` overrides either model.

54. **`AttributeSpec.keep_wording`**: attributes whose legal meaning a rewrite could shift are never sent to the rephrasing LLM. Set on `domicile_karnataka` after Gemini turned "domicile" into "native of Karnataka". Its registry question now reads "Are you legally domiciled in Karnataka (not just currently living there)?".

## Integration with Agent 1 (2026-10-31)

55. **`income` is an alias of `annual_family_income`**: Agent 1's `related_attribute` uses it.
56. **A known attribute with no operator is sent to the LLM for structuring** (previously only `None`/`unmapped:*`). Agent 1 delivers attribute + text without an operator; without this the rule stayed *Needs clarification* forever.
57. **`verified` needs both `source_url` and `evidence`**; the deterministic pass downgrades a verified rule missing either to `unverified`. Other statuses are left as they are.
58. **Compound criteria are split, never truncated.** The structuring LLM returns one item per condition (same id); later parts get ids `<id>_2`, `<id>_3`… and share the criterion and evidence. Conditions no attribute fits become `unmapped:<name>` (needs clarification), which keeps the scheme from *Potential match*. Found live: NSP's income + merit list + regular-course rule had kept only the income part. Dedup of LLM-structured rules keys on criterion + rule so a re-run keeps every part.
59. **Conditional limits are never verified.** If a structured rule's evidence states another threshold of similar size (0.25x-4x) that none of the rule's parts uses, e.g. "Rs 2.5 lakh for Category-I and Rs 1 lakh for Category 2A", its comparable parts become `uncertain` and the scheme gets an uncertainty note. Found live on the BCW post-matric rule. The number check also skips unmapped parts, whose value is a name, not a threshold.
60. **Select values must be stated in the evidence** (option or a listed synonym, whole words), for structured and extracted rules; otherwise `uncertain`. Found live: "post-matric education" was structured as `education_level eq Postgraduate`, which would have excluded every undergraduate.

## Build

16. **Phase order** follows the event schedule: 0, 1, 2, 3, 5 (questions), 4 (normalizer), 6 (planning). Review 1 needs questions, not the LLM.
17. Relative imports only, so the package can move under `backend/` unchanged.

## Notes for teammates

- **Member 1:** extract toward the attribute ids in `member2/attributes.py`. Requirements need `criterion`, `source_url` and a verbatim `evidence` quote; `attribute`/`operator`/`value` may be null. Documents should be objects `{name, source_url, evidence}`.
- **Member 3:** seed `answers` from the context form as `answered`. Normalize once at discovery and persist; call assess/questions afterwards. Pass everything after the first argument by keyword.
- **Members 3 & 4:** income answers are `{"min": number|null, "max": number|null}`. Question ids are opaque.
