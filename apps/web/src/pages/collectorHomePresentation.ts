import type { P85CollectorHomeRead } from "../api/client";

export const COLLECTOR_HOME_TITLE = "Collector Home";

export type SectionIndicatorStatus = "HAS_ITEMS" | "EMPTY" | "STALE" | "UNKNOWN" | "ERROR";

export const SECTION_LABELS: Record<string, string> = {
  buy_alerts: "Buy Opportunities",
  sell_alerts: "Sell Opportunities",
  grade_alerts: "Grade Candidates",
  foc_alerts: "FOC & Preorders",
  storage_issues: "Find a Book",
  marketplace_deals: "Buy Opportunities",
  future_pull_list: "Upcoming Releases",
};

/** Lowercase phrases for multi-section Today’s Actions summary. */
export const SECTION_OPPORTUNITY_PHRASE: Record<string, string> = {
  buy_alerts: "buy opportunities",
  sell_alerts: "sell opportunities",
  grade_alerts: "grade candidates",
  foc_alerts: "FOC and preorder opportunities",
  storage_issues: "books to locate",
  marketplace_deals: "buy opportunities",
  future_pull_list: "upcoming releases",
};

export const SECTION_EMPTY_MESSAGES: Record<string, string> = {
  buy_alerts: "No buy alerts right now",
  sell_alerts: "No sell alerts right now",
  grade_alerts: "No grade candidates right now",
  storage_issues: "No location issues found right now",
  marketplace_deals: "No buy deals right now",
  future_pull_list: "No upcoming release alerts right now",
  foc_alerts: "Review upcoming Final Order Cutoff decisions and preorder opportunities.",
};

/** Friendly copy when backend marks section SKIPPED (full data on dedicated page). */
export const SECTION_SKIPPED_LAUNCHER: Record<
  string,
  { body: string; button: string; to: string }
> = {
  buy_alerts: {
    body: "Review undervalued comics and marketplace deals identified by ComicOS.",
    button: "Review Buy Opportunities",
    to: "/buy-opportunities",
  },
  sell_alerts: {
    body: "Open the sell queue to review books that may be ready to sell.",
    button: "Review Sell Queue",
    to: "/sell-queue",
  },
  grade_alerts: {
    body: "Open grading tools to review books that may be worth grading.",
    button: "Review Grade Candidates",
    to: "/grade-before-sell",
  },
  foc_alerts: {
    body: "Review upcoming Final Order Cutoff decisions and preorder opportunities.",
    button: "Review FOC & Preorders",
    to: "/foc-dashboard",
  },
  storage_issues: {
    body: "Locate books, boxes, and storage locations across your collection.",
    button: "Find a Book",
    to: "/storage-dashboard",
  },
  future_pull_list: {
    body: "Review upcoming releases and books related to your collection interests.",
    button: "Review Upcoming Releases",
    to: "/future-pull-list",
  },
};

/** Links when section is OK but empty (items loaded, none to show). */
export const SECTION_EMPTY_ACTIONS: Record<string, { label: string; to: string }> = {
  buy_alerts: { label: "Review Buy Opportunities", to: "/buy-opportunities" },
  sell_alerts: { label: "Review Sell Queue", to: "/sell-queue" },
  grade_alerts: { label: "Review Grade Candidates", to: "/grade-before-sell" },
  foc_alerts: { label: "Review FOC & Preorders", to: "/foc-dashboard" },
  storage_issues: { label: "Find a Book", to: "/storage-dashboard" },
  marketplace_deals: { label: "Review Buy Opportunities", to: "/buy-opportunities" },
  future_pull_list: { label: "Review Upcoming Releases", to: "/future-pull-list" },
};

export type CollectorHomeDisplaySection = {
  key: string;
  title: string;
  items: Record<string, unknown>[];
  body: string;
  actionLabel: string;
  actionTo: string;
  showItems: boolean;
  indicatorText: string;
  indicatorShowCheck: boolean;
  indicatorTone: "has" | "empty" | "stale" | "unknown" | "error";
};

export function sectionIndicatorDisplay(sec: P85CollectorHomeRead["sections"][number]): {
  text: string;
  showCheck: boolean;
  tone: CollectorHomeDisplaySection["indicatorTone"];
} {
  const status = (sec.indicator_status ?? "UNKNOWN") as SectionIndicatorStatus;
  const count = sec.count;

  switch (status) {
    case "HAS_ITEMS":
      return {
        showCheck: true,
        tone: "has",
        text: count !== null && count !== undefined && count > 0 ? `${count} available` : "Available",
      };
    case "EMPTY":
      return { showCheck: false, tone: "empty", text: "No current alerts" };
    case "STALE":
      return { showCheck: false, tone: "stale", text: "Needs refresh" };
    case "ERROR":
      return { showCheck: false, tone: "error", text: "Unable to check" };
    case "UNKNOWN":
    default:
      return { showCheck: false, tone: "unknown", text: "Open to review" };
  }
}

export function buildCollectorHomeHeaderSummary(home: P85CollectorHomeRead): string {
  const parts: string[] = [];
  const portfolioRaw = home.portfolio_movement?.current_value;
  const portfolio =
    portfolioRaw !== null && portfolioRaw !== undefined && portfolioRaw !== ""
      ? Number(portfolioRaw)
      : null;
  if (portfolio !== null && !Number.isNaN(portfolio) && portfolio > 0 && home.portfolio_movement?.status === "OK") {
    parts.push(`Portfolio value: $${Math.round(portfolio).toLocaleString()}`);
  }
  const budgetRaw = home.budget_status?.monthly_budget;
  const budget =
    budgetRaw !== null && budgetRaw !== undefined && budgetRaw !== "" ? Number(budgetRaw) : null;
  const budgetState = String(home.budget_status?.state ?? "").toUpperCase();
  if (
    budget !== null &&
    !Number.isNaN(budget) &&
    budget > 0 &&
    home.budget_status?.status === "OK" &&
    budgetState !== "UNSET"
  ) {
    parts.push(`Monthly budget: $${Math.round(budget).toLocaleString()}`);
  }
  if (parts.length > 0) {
    return parts.join(" · ");
  }
  return "Your daily comic collecting command center";
}

export function homeHasSectionItemsReady(sections: P85CollectorHomeRead["sections"]): boolean {
  return sections.some(
    (s) => s.key !== "discovery_alerts" && s.indicator_status === "HAS_ITEMS",
  );
}

/** Compact line under Today's Actions when there are no daily action rows. */
export function buildTodaysActionsCompactSummary(sections: P85CollectorHomeRead["sections"]): string {
  const collapsed = collapseBuySectionsForSummary(sections);
  const actionable = collapsed
    .filter((s) => s.key !== "discovery_alerts" && s.indicator_status === "HAS_ITEMS")
    .map((section, index) => ({ section, index }))
    .sort((a, b) => {
      const rankDiff =
        indicatorStatusSortRank(a.section.indicator_status) -
        indicatorStatusSortRank(b.section.indicator_status);
      if (rankDiff !== 0) {
        return rankDiff;
      }
      const countDiff = (Number(b.section.count) || 0) - (Number(a.section.count) || 0);
      if (countDiff !== 0) {
        return countDiff;
      }
      return a.index - b.index;
    })
    .map(({ section }) => section);
  if (actionable.length === 0) {
    return "No immediate actions require attention.";
  }
  const hasNullCount = actionable.some((s) => s.count === null || s.count === undefined);
  if (hasNullCount) {
    return "Some dashboards have items ready for review.";
  }

  const withCounts = actionable
    .map((s) => ({
      key: s.key,
      count: Math.max(0, Number(s.count) || 0),
    }))
    .filter((row) => row.count > 0);

  if (withCounts.length === 0) {
    return "Some dashboards have items ready for review.";
  }

  if (withCounts.length === 1) {
    const row = withCounts[0];
    const label = SECTION_LABELS[row.key] ?? "Dashboard";
    return `${label} has ${row.count} opportunities ready for review.`;
  }

  const parts = withCounts.map((row) => {
    const phrase = SECTION_OPPORTUNITY_PHRASE[row.key] ?? "opportunities";
    return `${row.count} ${phrase}`;
  });
  if (parts.length === 2) {
    return `${parts[0]} and ${parts[1]} are ready for review.`;
  }
  return `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]} are ready for review.`;
}

const INDICATOR_SORT_RANK: Record<SectionIndicatorStatus, number> = {
  HAS_ITEMS: 0,
  STALE: 1,
  UNKNOWN: 2,
  EMPTY: 3,
  ERROR: 4,
};

export function indicatorStatusSortRank(status: string | null | undefined): number {
  const key = (status ?? "UNKNOWN") as SectionIndicatorStatus;
  return INDICATOR_SORT_RANK[key] ?? INDICATOR_SORT_RANK.UNKNOWN;
}

const BUY_HOME_SECTION_KEYS = ["buy_alerts", "marketplace_deals"] as const;

function pickStrongerSectionIndicator(
  a: P85CollectorHomeRead["sections"][number],
  b: P85CollectorHomeRead["sections"][number],
): P85CollectorHomeRead["sections"][number] {
  const rankA = indicatorStatusSortRank(a.indicator_status);
  const rankB = indicatorStatusSortRank(b.indicator_status);
  if (rankA !== rankB) {
    return rankA < rankB ? a : b;
  }
  if (a.indicator_status === "HAS_ITEMS" && b.indicator_status === "HAS_ITEMS") {
    const countA = Math.max(0, Number(a.count) || 0);
    const countB = Math.max(0, Number(b.count) || 0);
    return countB > countA ? b : a;
  }
  return a;
}

/** One buy card on Collector Home; backend may still send buy_alerts + marketplace_deals. */
function collapseBuySectionsForSummary(
  sections: P85CollectorHomeRead["sections"],
): P85CollectorHomeRead["sections"] {
  const buyParts = sections.filter((s) =>
    (BUY_HOME_SECTION_KEYS as readonly string[]).includes(s.key),
  );
  if (buyParts.length === 0) {
    return sections;
  }
  const mergedIndicator = buyParts.reduce(pickStrongerSectionIndicator);
  const withoutBuy = sections.filter(
    (s) => !(BUY_HOME_SECTION_KEYS as readonly string[]).includes(s.key),
  );
  return [...withoutBuy, { ...mergedIndicator, key: "buy_alerts" }];
}

function applyMergedBuyDisplay(
  buy: CollectorHomeDisplaySection,
  rawSections: P85CollectorHomeRead["sections"],
  extraIndicator?: P85CollectorHomeRead["sections"][number],
): void {
  const buyParts = rawSections.filter((s) =>
    (BUY_HOME_SECTION_KEYS as readonly string[]).includes(s.key),
  );
  if (buyParts.length === 0 && !extraIndicator?.indicator_status) {
    return;
  }
  let mergedRaw =
    buyParts.length > 0
      ? buyParts.reduce(pickStrongerSectionIndicator)
      : (extraIndicator as P85CollectorHomeRead["sections"][number]);
  if (extraIndicator?.indicator_status && buyParts.length > 0) {
    mergedRaw = pickStrongerSectionIndicator(mergedRaw, extraIndicator);
  }
  const indicator = sectionIndicatorDisplay(mergedRaw);
  buy.title = SECTION_LABELS.buy_alerts;
  buy.indicatorText = indicator.text;
  buy.indicatorShowCheck = indicator.showCheck;
  buy.indicatorTone = indicator.tone;

  const launcher = SECTION_SKIPPED_LAUNCHER.buy_alerts;
  if (!buy.showItems) {
    buy.body = launcher.body;
    buy.actionLabel = launcher.button;
    buy.actionTo = launcher.to;
  }
}

export function sortCollectorHomeSectionsForDisplay(
  sections: P85CollectorHomeRead["sections"],
): P85CollectorHomeRead["sections"] {
  const rest = sections.filter((s) => s.key !== "discovery_alerts");
  return rest
    .map((section, index) => ({ section, index }))
    .sort((a, b) => {
      const rankDiff = indicatorStatusSortRank(a.section.indicator_status) - indicatorStatusSortRank(b.section.indicator_status);
      if (rankDiff !== 0) {
        return rankDiff;
      }
      return a.index - b.index;
    })
    .map(({ section }) => section);
}

function sectionDisplay(sec: P85CollectorHomeRead["sections"][number]): CollectorHomeDisplaySection {
  const title = SECTION_LABELS[sec.key] ?? sec.title;
  const emptyAction = SECTION_EMPTY_ACTIONS[sec.key] ?? {
    label: "Learn more",
    to: "/discovery-dashboard",
  };
  const launcher = SECTION_SKIPPED_LAUNCHER[sec.key];
  const emptyMessage = SECTION_EMPTY_MESSAGES[sec.key] ?? "Nothing to show right now.";
  const indicator = sectionIndicatorDisplay(sec);

  const base = {
    key: sec.key,
    title,
    indicatorText: indicator.text,
    indicatorShowCheck: indicator.showCheck,
    indicatorTone: indicator.tone,
  };

  if (sec.status === "ERROR") {
    return {
      ...base,
      items: [],
      body: "Unable to load this section right now.",
      actionLabel: emptyAction.label,
      actionTo: emptyAction.to,
      showItems: false,
    };
  }

  if (sec.status === "SKIPPED") {
    const fallback = launcher ?? {
      body: "Open the dedicated page for full details.",
      button: emptyAction.label,
      to: emptyAction.to,
    };
    return {
      ...base,
      items: [],
      body: fallback.body,
      actionLabel: fallback.button,
      actionTo: fallback.to,
      showItems: false,
    };
  }

  const hasItems = sec.items.length > 0;
  if (hasItems) {
    return {
      ...base,
      items: sec.items,
      body: "",
      actionLabel: emptyAction.label,
      actionTo: emptyAction.to,
      showItems: true,
    };
  }

  return {
    ...base,
    items: [],
    body: emptyMessage,
    actionLabel: emptyAction.label,
    actionTo: emptyAction.to,
    showItems: false,
  };
}

/** Merge discovery into buy display; collapse duplicate buy cards. */
export function prepareCollectorHomeSections(
  sections: P85CollectorHomeRead["sections"],
): CollectorHomeDisplaySection[] {
  const discovery = sections.find((s) => s.key === "discovery_alerts");
  const sorted = sortCollectorHomeSectionsForDisplay(sections);
  const prepared = sorted.map(sectionDisplay);

  const buy = prepared.find((s) => s.key === "buy_alerts");
  const marketplace = prepared.find((s) => s.key === "marketplace_deals");

  if (buy && marketplace) {
    buy.items = [...buy.items, ...marketplace.items];
    buy.showItems = buy.items.length > 0;
    if (buy.showItems) {
      buy.body = "";
    }
  } else if (marketplace && !buy) {
    marketplace.key = "buy_alerts";
    marketplace.title = SECTION_LABELS.buy_alerts;
  }

  const buyCard = prepared.find((s) => s.key === "buy_alerts") ?? marketplace;
  if (discovery && buyCard) {
    if (discovery.items.length > 0) {
      buyCard.items = [...buyCard.items, ...discovery.items];
      buyCard.showItems = buyCard.items.length > 0;
      if (buyCard.showItems) {
        buyCard.body = "";
      }
    }
  }
  if (buyCard) {
    applyMergedBuyDisplay(buyCard, sections, discovery);
  }

  return prepared
    .filter((s) => s.key !== "discovery_alerts" && s.key !== "marketplace_deals")
    .map((section, index) => ({ section, index }))
    .sort((a, b) => {
      const rankDiff = displaySectionSortRank(a.section) - displaySectionSortRank(b.section);
      if (rankDiff !== 0) {
        return rankDiff;
      }
      return a.index - b.index;
    })
    .map(({ section }) => section);
}

function displaySectionSortRank(section: CollectorHomeDisplaySection): number {
  switch (section.indicatorTone) {
    case "has":
      return INDICATOR_SORT_RANK.HAS_ITEMS;
    case "stale":
      return INDICATOR_SORT_RANK.STALE;
    case "unknown":
      return INDICATOR_SORT_RANK.UNKNOWN;
    case "empty":
      return INDICATOR_SORT_RANK.EMPTY;
    case "error":
      return INDICATOR_SORT_RANK.ERROR;
    default:
      return INDICATOR_SORT_RANK.UNKNOWN;
  }
}

export function itemLabel(item: Record<string, unknown>): string {
  const title = item.title ?? item.label;
  if (title !== undefined && title !== null && String(title).trim()) {
    return String(title);
  }
  return "Item";
}

export function indicatorBadgeClassName(tone: CollectorHomeDisplaySection["indicatorTone"]): string {
  switch (tone) {
    case "has":
      return "bg-emerald-50 text-emerald-800 ring-emerald-200";
    case "stale":
      return "bg-amber-50 text-amber-900 ring-amber-200";
    case "error":
      return "bg-red-50 text-red-800 ring-red-200";
    case "empty":
      return "bg-slate-100 text-slate-700 ring-slate-200";
    case "unknown":
    default:
      return "bg-amber-50 text-amber-900 ring-amber-200";
  }
}
