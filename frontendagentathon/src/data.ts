// FICTIONAL DEMO DATA — not real schemes. Swap for the live API when it exists.

export const CATEGORIES = ["Scholarships", "Fee concessions", "Healthcare", "Pensions", "Subsidies"] as const;
export type Category = (typeof CATEGORIES)[number];

export type Status = "ok" | "info" | "nv" | "unclear" | "warn";
export type Pip = "ok" | "no" | "unk" | "unv";
export type SourceType = "verified" | "fallback" | "user-reported" | "simulated";

/** Where a criterion's input comes from: a question on the Questions page, or a field from the Context form. */
export type CriterionSource = { kind: "question"; id: string } | { kind: "detail"; field: "age" };
export type CriterionTest = { oneOf: readonly string[] } | { min: number };

export type Criterion = {
  id: string;
  /** The published rule, quoted (fictional demo text). */
  rule: string;
  /** What we call the missing information when this can't be checked yet. */
  missing: string;
  source: CriterionSource;
  test: CriterionTest;
};

/** The five income brackets are in QUESTIONS; these are the ones within the ₹2.5 lakh demo limit. */
const WITHIN_INCOME_LIMIT = ["Under ₹1 lakh", "₹1–2.5 lakh"] as const;

export type Scheme = {
  id: string;
  name: string;
  dept: string;
  summary: string;
  /** false = the rules couldn't be confirmed from an official source, so they are never evaluated. */
  verified: boolean;
  /** Evaluated against the user's saved answers in eligibility.ts; status, counts and text are derived, not stored. */
  criteria: Criterion[];
  url: string;
  fallback?: boolean;
  sourceType: SourceType;
  lastVerified: string;
};

const DOMICILE: Criterion = {
  id: "dom", rule: "Applicant must be a resident of Karnataka.", missing: "Karnataka domicile",
  source: { kind: "question", id: "dom" }, test: { oneOf: ["Yes"] },
};
const INCOME: Criterion = {
  id: "income", rule: "Annual family income up to ₹2.5 lakh.", missing: "family income",
  source: { kind: "question", id: "income" }, test: { oneOf: WITHIN_INCOME_LIMIT },
};

export const SCHEMES: Scheme[] = [
  {
    id: "c", name: "Demo Merit Award C", dept: "STATE · HIGHER EDUCATION (DEMO)", verified: true,
    summary: "Annual award for students with strong Class 12 results.",
    criteria: [
      { id: "edu", rule: "Must be studying in Class 12 / PUC.", missing: "course level", source: { kind: "question", id: "edu" }, test: { oneOf: ["Class 12 / PUC"] } },
      DOMICILE,
    ],
    url: "https://example.gov.in/merit-award-c", sourceType: "verified", lastVerified: "Oct 2026",
  },
  {
    id: "a", name: "Demo Scholarship A", dept: "STATE · COLLEGIATE EDUCATION (DEMO)", verified: true,
    summary: "Scholarship for undergraduates from lower-income families.",
    criteria: [
      { id: "edu", rule: "Must be enrolled in an undergraduate degree course.", missing: "course level", source: { kind: "question", id: "edu" }, test: { oneOf: ["Undergraduate"] } },
      DOMICILE,
      INCOME,
    ],
    url: "https://example.gov.in/scholarship-a", sourceType: "verified", lastVerified: "Oct 2026",
  },
  {
    id: "b", name: "Demo Fee Concession B", dept: "STATE · TECHNICAL EDUCATION (DEMO)", verified: true,
    summary: "Partial tuition fee waiver at eligible institutions.",
    criteria: [
      { id: "edu", rule: "Must be enrolled in a diploma or degree course.", missing: "course level", source: { kind: "question", id: "edu" }, test: { oneOf: ["Diploma", "Undergraduate"] } },
      { id: "inst", rule: "Must study at a government or government-aided institution.", missing: "institution type", source: { kind: "question", id: "inst" }, test: { oneOf: ["Government", "Government-aided"] } },
      INCOME,
    ],
    url: "https://example.gov.in/fee-concession-b", sourceType: "verified", lastVerified: "Oct 2026",
  },
  {
    id: "d", name: "Demo Housing Aid D", dept: "STATE · SOCIAL WELFARE (DEMO)", verified: false, fallback: true,
    summary: "Rent support for students living away from home.",
    criteria: [
      DOMICILE,
      { id: "edu", rule: "Must be enrolled in a course.", missing: "course level", source: { kind: "question", id: "edu" }, test: { oneOf: ["Diploma", "Undergraduate", "Postgraduate"] } },
      { id: "inst", rule: "Must study away from home.", missing: "institution type", source: { kind: "question", id: "inst" }, test: { oneOf: ["Government", "Government-aided", "Private unaided"] } },
    ],
    url: "https://example.gov.in/housing-aid-d", sourceType: "fallback", lastVerified: "Unverified lead",
  },
  {
    id: "e", name: "Demo Pension E", dept: "STATE · REVENUE (DEMO)", verified: true,
    summary: "Monthly pension for older residents.",
    criteria: [
      { id: "age", rule: "Applicant must be 60 years or older.", missing: "age", source: { kind: "detail", field: "age" }, test: { min: 60 } },
      DOMICILE,
    ],
    url: "https://example.gov.in/pension-e", sourceType: "verified", lastVerified: "Oct 2026",
  },
];
export type Question = {
  id: string;
  text: string;
  why: string;
  sensitive: boolean;
  allowPrefer: boolean;
  opts: string[];
};

export const QUESTIONS: Question[] = [
  {
    id: "income", text: "What's your family's annual income?",
    why: "Two schemes set an income limit. We only keep the bracket, never an exact figure.",
    sensitive: true, allowPrefer: true,
    opts: ["Under ₹1 lakh", "₹1–2.5 lakh", "₹2.5–5 lakh", "₹5–8 lakh", "Above ₹8 lakh"],
  },
  {
    id: "inst", text: "What type of institution do you study at?",
    why: "Fee Concession B only covers some institution types.",
    sensitive: false, allowPrefer: false,
    opts: ["Government", "Government-aided", "Private unaided", "Not enrolled yet"],
  },
  {
    id: "dom", text: "Do you have Karnataka domicile?",
    why: "Most state schemes ask for proof that you live in the state.",
    sensitive: false, allowPrefer: false,
    opts: ["Yes", "No"],
  },
  {
    id: "edu", text: "What are you studying right now?",
    why: "Scholarships are usually tied to a course level.",
    sensitive: false, allowPrefer: false,
    opts: ["Class 12 / PUC", "Diploma", "Undergraduate", "Postgraduate"],
  },
];


export type DocStatus = "needed" | "have" | "obtained";

/** The user's own report of where an application stands. Only the authority decides the outcome. */
export type ApplyStage = "todo" | "submitted" | "approved" | "received";
export const APPLY_STAGES: [ApplyStage, string][] = [
  ["todo", "Not started"], ["submitted", "Submitted"], ["approved", "Approved"], ["received", "Benefit received"],
];

export type PlanDoc = {
  id: string;
  name: string;
  reason: string;
  for: string[];
  shared?: boolean;
  after?: string;
  url: string;
};

export const PLAN_DOCS: PlanDoc[] = [
  { id: "income", name: "Income Certificate", reason: "Proves your family income for the income limit.", for: ["Demo Scholarship A", "Demo Fee Concession B"], shared: true, url: "https://example.gov.in/income-certificate" },
  { id: "domicile", name: "Domicile Certificate", reason: "Proves you live in Karnataka. You need it before applying for a Caste Certificate.", for: ["Demo Merit Award C"], url: "https://example.gov.in/domicile-certificate" },
  { id: "caste", name: "Caste Certificate", reason: "Required for the fee concession category.", for: ["Demo Fee Concession B"], after: "Domicile Certificate", url: "https://example.gov.in/caste-certificate" },
  { id: "admission", name: "Admission Letter", reason: "Shows you're enrolled in an eligible course.", for: ["Demo Scholarship A"], url: "https://example.gov.in/scholarship-a/notice" },
  { id: "fee", name: "Fee Receipt", reason: "Shows the fees you've paid this year.", for: ["Demo Fee Concession B"], url: "https://example.gov.in/fee-concession-b" },
];

/** Document → scheme edges in the "what each document unlocks" graph. */
export const PLAN_EDGES: { doc: string; scheme: "a" | "b" | "c"; d: string }[] = [
  { doc: "income", scheme: "a", d: "M194 24 C262 24 262 54 330 54" },
  { doc: "income", scheme: "b", d: "M194 24 C262 24 262 150 330 150" },
  { doc: "domicile", scheme: "c", d: "M194 84 C262 84 262 246 330 246" },
  { doc: "caste", scheme: "b", d: "M194 144 C262 144 262 150 330 150" },
  { doc: "admission", scheme: "a", d: "M194 204 C262 204 262 54 330 54" },
  { doc: "fee", scheme: "b", d: "M194 264 C262 264 262 150 330 150" },
];

export const PLAN_SCHEME_NODES = [
  { id: "a", label: "Demo Scholarship A", top: 32 },
  { id: "b", label: "Demo Fee Concession B", top: 128 },
  { id: "c", label: "Demo Merit Award C", top: 224 },
] as const;
