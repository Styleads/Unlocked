// FICTIONAL DEMO DATA — not real schemes. Swap for the live API when it exists.

export const CATEGORIES = ["Scholarships", "Fee concessions", "Healthcare", "Pensions", "Subsidies"] as const;
export type Category = (typeof CATEGORIES)[number];

export type Status = "ok" | "info" | "nv" | "unclear" | "warn";
export type Pip = "ok" | "no" | "unk" | "unv";
export type SourceType = "verified" | "fallback" | "user-reported" | "simulated";

export type Scheme = {
  id: string;
  name: string;
  dept: string;
  status: Exclude<Status, "unclear">;
  summary: string;
  expl: string;
  pips: Pip[];
  met: number;
  missing: string[];
  url: string;
  fallback?: boolean;
  sourceType: SourceType;
  lastVerified: string;
};

export const SCHEMES: Scheme[] = [
  {
    id: "c", name: "Demo Merit Award C", dept: "STATE · HIGHER EDUCATION (DEMO)", status: "ok",
    summary: "Annual award for students with strong Class 12 results.",
    expl: "Your education level and domicile meet the two criteria we checked.",
    pips: ["ok", "ok"], met: 2, missing: [], url: "https://example.gov.in/merit-award-c",
    sourceType: "verified", lastVerified: "Oct 2026",
  },
  {
    id: "a", name: "Demo Scholarship A", dept: "STATE · COLLEGIATE EDUCATION (DEMO)", status: "info",
    summary: "Scholarship for undergraduates from lower-income families.",
    expl: "Your course qualifies. We still need your family income to check the income limit.",
    pips: ["ok", "ok", "unk"], met: 2, missing: ["family income"], url: "https://example.gov.in/scholarship-a",
    sourceType: "verified", lastVerified: "Oct 2026",
  },
  {
    id: "b", name: "Demo Fee Concession B", dept: "STATE · TECHNICAL EDUCATION (DEMO)", status: "info",
    summary: "Partial tuition fee waiver at eligible institutions.",
    expl: "Depends on your institution type and family income, which you haven't shared yet.",
    pips: ["ok", "unk", "unk"], met: 1, missing: ["family income", "institution type"], url: "https://example.gov.in/fee-concession-b",
    sourceType: "verified", lastVerified: "Oct 2026",
  },
  {
    id: "d", name: "Demo Housing Aid D", dept: "STATE · SOCIAL WELFARE (DEMO)", status: "nv", fallback: true,
    summary: "Rent support for students living away from home.",
    expl: "We couldn't confirm these rules from an official source yet, so we haven't checked them.",
    pips: ["unv", "unv", "unv"], met: 0, missing: [], url: "https://example.gov.in/housing-aid-d",
    sourceType: "fallback", lastVerified: "Unverified lead",
  },
  {
    id: "e", name: "Demo Pension E", dept: "STATE · REVENUE (DEMO)", status: "warn",
    summary: "Monthly pension for older residents.",
    expl: "Your age appears not to meet the stated minimum age.",
    pips: ["no", "ok"], met: 1, missing: [], url: "https://example.gov.in/pension-e",
    sourceType: "verified", lastVerified: "Oct 2026",
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

/** Income brackets within Demo Scholarship A's ₹2.5 lakh limit. */
export const INCOME_WITHIN_LIMIT = new Set(["Under ₹1 lakh", "₹1–2.5 lakh"]);

export type DocStatus = "needed" | "have" | "obtained";

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
