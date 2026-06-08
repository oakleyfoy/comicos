/** P91-01 — extensible onboarding step registry (add future steps here). */

export type OnboardingStepId =
  | "collector_type"
  | "risk_tolerance"
  | "time_horizon"
  | "publishers"
  | "characters"
  | "creators"
  | "preview";

export type OnboardingStepDef = {
  id: OnboardingStepId;
  title: string;
  subtitle: string;
};

export const ONBOARDING_STEPS: OnboardingStepDef[] = [
  {
    id: "collector_type",
    title: "What kind of collector are you?",
    subtitle: "Choose the style that best matches how you buy and enjoy comics.",
  },
  {
    id: "risk_tolerance",
    title: "How much risk feels right?",
    subtitle: "Risk tolerance directly affects recommendation rankings.",
  },
  {
    id: "time_horizon",
    title: "What is your time horizon?",
    subtitle: "How long you plan to hold books shapes which releases we surface first.",
  },
  {
    id: "publishers",
    title: "Favorite publishers",
    subtitle: "Search ComicOS catalog publishers — no typing required.",
  },
  {
    id: "characters",
    title: "Favorite characters",
    subtitle: "Pick the heroes and teams you want ComicOS to watch.",
  },
  {
    id: "creators",
    title: "Favorite creators",
    subtitle: "Writers and artists whose work you always follow.",
  },
  {
    id: "preview",
    title: "Your collector profile",
    subtitle: "Review how ComicOS will personalize recommendations.",
  },
];

export const TOTAL_ONBOARDING_STEPS = ONBOARDING_STEPS.length;

export type CollectorTypeValue = "INVESTOR" | "SPECULATOR" | "COMPLETIONIST" | "READER" | "HYBRID";
export type RiskProfileValue = "CONSERVATIVE" | "MODERATE" | "AGGRESSIVE";
export type TimeHorizonValue =
  | "SHORT_TERM_FLIP"
  | "MEDIUM_TERM"
  | "LONG_TERM"
  | "MIXED";

export const COLLECTOR_TYPE_CARDS: {
  value: CollectorTypeValue;
  title: string;
  description: string;
  behavior: string;
  examples: string[];
  icon: string;
}[] = [
  {
    value: "INVESTOR",
    title: "Investor",
    description: "Focuses on long-term value appreciation.",
    behavior: "Buys keys and holds for portfolio growth.",
    examples: ["Key issues", "First appearances", "CGC candidates", "Long-term holds"],
    icon: "📈",
  },
  {
    value: "SPECULATOR",
    title: "Speculator",
    description: "Focuses on future catalysts and market momentum.",
    behavior: "Tracks hype cycles and catalyst-driven upside.",
    examples: ["New characters", "Movie rumors", "TV announcements", "Quick flips"],
    icon: "⚡",
  },
  {
    value: "COMPLETIONIST",
    title: "Completionist",
    description: "Focuses on completing runs and collections.",
    behavior: "Fills gaps and chases full runs.",
    examples: ["Missing issues", "Run completion", "Collection goals"],
    icon: "✅",
  },
  {
    value: "READER",
    title: "Reader",
    description: "Focuses primarily on reading enjoyment.",
    behavior: "Prioritizes story quality and discovery.",
    examples: ["Story arcs", "Reading recommendations", "Creator discovery"],
    icon: "📖",
  },
  {
    value: "HYBRID",
    title: "Hybrid",
    description: "Combines collecting, investing, and reading.",
    behavior: "Balances keys, runs, and great stories.",
    examples: ["Mixed goals", "Flexible holds", "Broad discovery"],
    icon: "🎯",
  },
];

export const RISK_CARDS: {
  value: RiskProfileValue;
  title: string;
  summary: string;
  examples?: string[];
}[] = [
  {
    value: "CONSERVATIVE",
    title: "Conservative",
    summary: "Established keys, blue-chip characters, lower volatility.",
    examples: ["Batman", "Spider-Man", "X-Men"],
  },
  {
    value: "MODERATE",
    title: "Balanced",
    summary: "Mix of established keys and emerging opportunities.",
  },
  {
    value: "AGGRESSIVE",
    title: "Aggressive",
    summary: "New #1 issues, indie books, new first appearances, high-upside speculation.",
  },
];

export const HORIZON_CARDS: {
  value: TimeHorizonValue;
  title: string;
  range: string;
  focus: string;
}[] = [
  {
    value: "SHORT_TERM_FLIP",
    title: "Short-Term",
    range: "0–12 months",
    focus: "Flips, market momentum, upcoming catalysts",
  },
  {
    value: "MEDIUM_TERM",
    title: "Medium-Term",
    range: "1–5 years",
    focus: "Franchise growth and character development",
  },
  {
    value: "LONG_TERM",
    title: "Long-Term",
    range: "5+ years",
    focus: "Historical significance, major keys, legacy characters",
  },
  {
    value: "MIXED",
    title: "Mixed",
    range: "All horizons",
    focus: "Combination of short-, medium-, and long-term goals",
  },
];
