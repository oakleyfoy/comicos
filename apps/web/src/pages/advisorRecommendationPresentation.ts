import type { P90AdvisorActionRead, P90AdvisorTodayActionRead } from "../api/client";

const TITLE_PREFIXES = [
  "Strong Buy: ",
  "Good Buy: ",
  "Spec Buy: ",
  "Undervalued: ",
  "Buy opportunity: ",
  "Buy: ",
  "Sell now: ",
  "Monitor sell: ",
  "Grade first: ",
  "Watch: ",
  "Review stale listing: ",
  "Review expired listing: ",
];

const CATEGORY_TITLE_PREFIXES: Record<string, RegExp> = {
  BUY: /^(buy\s+)+/i,
  SELL: /^(sell\s+)+/i,
  GRADE: /^(grade\s+)+/i,
  WATCH: /^(watch\s+)+/i,
};

export const MAX_VISIBLE_EVIDENCE = 3;

export function splitEvidenceSegments(text: string): string[] {
  const raw = text.trim();
  if (!raw) return [];
  const parts = raw
    .split(/\s*[·|,;]\s*|\s+\/\s+/)
    .map((p) => p.trim())
    .filter(Boolean);
  return parts.length ? parts : [raw];
}

export function dedupeEvidenceSegments(segments: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const segment of segments) {
    const text = segment.replace(/\s+/g, " ").trim();
    if (!text) continue;
    const key = text.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(text);
  }
  return out;
}

export function dedupeEvidenceString(text: string): string {
  return dedupeEvidenceSegments(splitEvidenceSegments(text)).join(" · ");
}

export function formatEvidenceDisplay(text: string, maxVisible = MAX_VISIBLE_EVIDENCE): {
  primary: string;
  supporting: string[];
  hiddenCount: number;
} {
  const unique = dedupeEvidenceSegments(splitEvidenceSegments(text));
  if (!unique.length) {
    return { primary: "", supporting: [], hiddenCount: 0 };
  }
  const primary = unique[0];
  const supporting = unique.slice(1, maxVisible);
  const hiddenCount = Math.max(0, unique.length - maxVisible);
  return { primary, supporting, hiddenCount };
}

export function stripAdvisorTitlePrefixes(title: string, category?: string): string {
  let text = title.trim();
  for (const prefix of TITLE_PREFIXES) {
    if (text.startsWith(prefix)) {
      text = text.slice(prefix.length).trim();
      break;
    }
  }
  const cat = (category || "").toUpperCase();
  const catRe = CATEGORY_TITLE_PREFIXES[cat];
  if (catRe) {
    text = text.replace(catRe, "").trim();
  }
  for (const prefix of TITLE_PREFIXES) {
    if (text.startsWith(prefix)) {
      text = text.slice(prefix.length).trim();
    }
  }
  return text;
}

export function cleanActionTitle(action: Pick<P90AdvisorActionRead, "comic" | "display_label" | "category">): string {
  const raw = action.comic?.trim() || action.display_label?.trim() || "";
  return stripAdvisorTitlePrefixes(raw, action.category);
}

export function cleanTodayActionTitle(action: Pick<P90AdvisorTodayActionRead, "title" | "category">): string {
  return stripAdvisorTitlePrefixes(action.title, action.category);
}

export function categoryRecommendationLabel(category: string): string {
  switch (category.toUpperCase()) {
    case "BUY":
      return "Buy recommendation";
    case "SELL":
      return "Sell recommendation";
    case "GRADE":
      return "Grade recommendation";
    case "WATCH":
      return "Watch recommendation";
    default:
      return "Recommendation";
  }
}

export function actionValueMetric(action: {
  category?: string;
  potential_upside?: number | null;
  profit_potential?: number | null;
  value_increase?: number | null;
}): { label: string; amount: number } | null {
  const cat = (action.category || "").toUpperCase();
  if (cat === "BUY" && action.potential_upside != null && action.potential_upside > 0) {
    return { label: "Estimated savings", amount: action.potential_upside };
  }
  if (cat === "SELL" && action.profit_potential != null && action.profit_potential > 0) {
    return { label: "Estimated profit", amount: action.profit_potential };
  }
  if (cat === "GRADE" && action.value_increase != null && action.value_increase > 0) {
    return { label: "Grade upside", amount: action.value_increase };
  }
  return null;
}

export function resolveActionEvidence(action: P90AdvisorActionRead): {
  primary: string;
  supporting: string[];
  hiddenCount: number;
} {
  const merged = dedupeEvidenceString(action.primary_reason || action.reason || "");
  if (action.supporting_signals?.length) {
    const primary = action.primary_reason || merged.split(" · ")[0] || merged;
    const supporting = dedupeEvidenceSegments([
      ...action.supporting_signals,
      ...splitEvidenceSegments(merged).slice(1),
    ]).slice(0, MAX_VISIBLE_EVIDENCE - 1);
    const total = dedupeEvidenceSegments(splitEvidenceSegments(merged)).length;
    return {
      primary,
      supporting,
      hiddenCount: Math.max(0, total - MAX_VISIBLE_EVIDENCE),
    };
  }
  return formatEvidenceDisplay(merged);
}

export function planHasEmptySecondarySections(plan: {
  sell_actions: unknown[];
  grade_actions: unknown[];
  watch_actions: unknown[];
  market_alerts: unknown[];
  recent_activity: unknown[];
}): boolean {
  return (
    plan.sell_actions.length === 0 &&
    plan.grade_actions.length === 0 &&
    plan.watch_actions.length === 0 &&
    plan.market_alerts.length === 0 &&
    plan.recent_activity.length === 0
  );
}
