import type { P85CollectorHomeRead } from "../api/client";

export const COLLECTOR_HOME_TITLE = "Collector Home";

export const COLLECTOR_HOME_MONITORING_MESSAGE =
  "Ready for your collection. ComicOS will surface buy, sell, grading, and release opportunities here as you import comics and activity grows.";

export const COLLECTOR_HOME_READY_TAGLINE =
  "Ready for your collection — import comics to unlock portfolio value and daily opportunities.";

export const COLLECTOR_HOME_ADVISOR_SUMMARY =
  "Collector Advisor turns your collection signals into a prioritized daily plan for buys, sells, grading, and releases.";

export const STRIP_COLLECTION_VALUE_EMPTY = "Import comics to calculate";
export const STRIP_ZERO = "0";
export const STRIP_LOADING = "Loading";

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
    body: "Review buy recommendations and marketplace opportunities.",
    button: "Open Buy Opportunities",
    to: "/buy-opportunities",
  },
  sell_alerts: {
    body: "See sell candidates, drafts, listings, and profit in one place.",
    button: "Open Sell Command Center",
    to: "/sell-command-center",
  },
  grade_alerts: {
    body: "Review books that may be worth grading before you sell.",
    button: "Open Grade Candidates",
    to: "/grade-before-sell",
  },
  foc_alerts: {
    body: "Track Final Order Cutoff deadlines and preorder decisions.",
    button: "Open FOC Dashboard",
    to: "/foc-dashboard",
  },
  storage_issues: {
    body: "Locate books, boxes, and storage across your collection.",
    button: "Find a Book",
    to: "/storage-dashboard",
  },
  future_pull_list: {
    body: "See upcoming releases tied to your collection interests.",
    button: "Open Upcoming Releases",
    to: "/future-pull-list",
  },
};

/** Links when section is OK but empty (items loaded, none to show). */
export const SECTION_EMPTY_ACTIONS: Record<string, { label: string; to: string }> = {
  buy_alerts: { label: "Open Buy Opportunities", to: "/buy-opportunities" },
  sell_alerts: { label: "Open Sell Command Center", to: "/sell-command-center" },
  grade_alerts: { label: "Open Grade Candidates", to: "/grade-before-sell" },
  foc_alerts: { label: "Open FOC Dashboard", to: "/foc-dashboard" },
  storage_issues: { label: "Find a Book", to: "/storage-dashboard" },
  marketplace_deals: { label: "Open Buy Opportunities", to: "/buy-opportunities" },
  future_pull_list: { label: "Open Upcoming Releases", to: "/future-pull-list" },
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
  indicatorTone: "has" | "empty" | "stale" | "unknown" | "error" | "static";
};

/** Semantic badges for launcher-style cards (never generic "Review"). */
const STATIC_SECTION_BADGE: Record<string, string> = {
  portfolio: "Portfolio",
  storage_issues: "Search",
  future_pull_list: "Upcoming",
  foc_alerts: "FOC",
};

export function sectionIndicatorDisplay(
  sec: P85CollectorHomeRead["sections"][number],
  options?: { staticBadgeKey?: string },
): {
  text: string;
  showCheck: boolean;
  tone: CollectorHomeDisplaySection["indicatorTone"];
} {
  const status = (sec.indicator_status ?? "UNKNOWN") as SectionIndicatorStatus;
  const count = sec.count;
  const staticKey = options?.staticBadgeKey ?? sec.key;

  switch (status) {
    case "HAS_ITEMS":
      if (count !== null && count !== undefined && count > 0) {
        return { showCheck: true, tone: "has", text: `${count} Available` };
      }
      return { showCheck: false, tone: "empty", text: "No Alerts" };
    case "EMPTY":
      return { showCheck: false, tone: "empty", text: "No Alerts" };
    case "STALE":
      return { showCheck: false, tone: "empty", text: "No Alerts" };
    case "ERROR":
      return { showCheck: false, tone: "empty", text: "No Alerts" };
    case "UNKNOWN":
    default:
      if (STATIC_SECTION_BADGE[staticKey]) {
        return {
          showCheck: false,
          tone: "static",
          text: STATIC_SECTION_BADGE[staticKey],
        };
      }
      return { showCheck: false, tone: "empty", text: "No Alerts" };
  }
}

export function formatSectionTitleWithCount(
  baseTitle: string,
  sec: P85CollectorHomeRead["sections"][number] | { count?: number | null; key?: string },
): string {
  if (sec.key === "portfolio") {
    return baseTitle;
  }
  if (sec.count === null || sec.count === undefined) {
    return baseTitle;
  }
  return `${baseTitle} (${sec.count})`;
}

export function buildCollectorHomeHeaderSummary(home: P85CollectorHomeRead): string {
  if (home.advisor_plan_ready && home.advisor_total_actions != null && home.advisor_total_actions > 0) {
    return `${home.advisor_total_actions} actions ready — open Collector Advisor for your daily plan.`;
  }
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
  return COLLECTOR_HOME_READY_TAGLINE;
}

export type DashboardStripMetric = {
  label: string;
  value: string;
};

const DASHBOARD_STRIP_LABELS = [
  "Collection Value",
  "Books Owned",
  "Open Opportunities",
  "Potential Profit",
] as const;

const OPPORTUNITY_STRIP_KEYS = new Set([
  "buy_alerts",
  "sell_alerts",
  "grade_alerts",
  "foc_alerts",
  "future_pull_list",
]);

function countOpenOpportunities(sections: P85CollectorHomeRead["sections"]): number {
  const collapsed = collapseBuySectionsForSummary(sections);
  let sum = 0;
  for (const sec of collapsed) {
    if (!OPPORTUNITY_STRIP_KEYS.has(sec.key)) {
      continue;
    }
    if (sec.indicator_status === "ERROR") {
      continue;
    }
    if (sec.count === null || sec.count === undefined) {
      continue;
    }
    sum += Math.max(0, Number(sec.count) || 0);
  }
  return sum;
}

function formatPotentialProfit(pm: Record<string, unknown>, pmStatus: string): string {
  const gainRaw = pm.unrealized_gain ?? pm.net_profit ?? pm.total_unrealized_gain;
  if (pmStatus === "OK" && gainRaw !== null && gainRaw !== undefined && gainRaw !== "") {
    const gain = Number(gainRaw);
    if (!Number.isNaN(gain)) {
      const sign = gain >= 0 ? "" : "-";
      return `${sign}$${Math.round(Math.abs(gain)).toLocaleString()}`;
    }
  }
  if (pmStatus === "OK") {
    return "$0";
  }
  return STRIP_ZERO;
}

export function buildDashboardStripLoading(): DashboardStripMetric[] {
  return DASHBOARD_STRIP_LABELS.map((label) => ({ label, value: STRIP_LOADING }));
}

/** Always four columns; uses cached collector-home fields only. */
export function buildDashboardStrip(home: P85CollectorHomeRead): DashboardStripMetric[] {
  const pm = home.portfolio_movement ?? {};
  const pmStatus = String(pm.status ?? "").toUpperCase();
  const valueRaw = pm.current_value;
  const value =
    valueRaw !== null && valueRaw !== undefined && valueRaw !== "" ? Number(valueRaw) : null;
  let collectionValue = STRIP_COLLECTION_VALUE_EMPTY;
  if (pmStatus === "OK" && value !== null && !Number.isNaN(value) && value > 0) {
    collectionValue = `$${Math.round(value).toLocaleString()}`;
  } else if (pmStatus === "OK" && value !== null && !Number.isNaN(value) && value === 0) {
    collectionValue = "$0";
  }

  const booksRaw = pm.books_owned ?? pm.book_count;
  let booksOwned = STRIP_ZERO;
  if (pmStatus === "OK" && booksRaw !== null && booksRaw !== undefined && booksRaw !== "") {
    const books = Number(booksRaw);
    if (!Number.isNaN(books)) {
      booksOwned = String(Math.round(books));
    }
  }

  const openOpportunities = String(countOpenOpportunities(home.sections));
  const potentialProfit = formatPotentialProfit(pm, pmStatus);

  return [
    { label: DASHBOARD_STRIP_LABELS[0], value: collectionValue },
    { label: DASHBOARD_STRIP_LABELS[1], value: booksOwned },
    { label: DASHBOARD_STRIP_LABELS[2], value: openOpportunities },
    { label: DASHBOARD_STRIP_LABELS[3], value: potentialProfit },
  ];
}

/** @deprecated use buildDashboardStrip */
export function buildPortfolioStrip(home: P85CollectorHomeRead): DashboardStripMetric[] {
  return buildDashboardStrip(home);
}

const TODAY_SUMMARY_KEYS: { key: string; label: string }[] = [
  { key: "buy_alerts", label: "Buy Opportunities" },
  { key: "sell_alerts", label: "Sell Opportunities" },
  { key: "grade_alerts", label: "Grade Candidates" },
  { key: "future_pull_list", label: "Upcoming Releases" },
];

function sectionCountForSummary(
  sections: P85CollectorHomeRead["sections"],
  key: string,
): number | null {
  const collapsed = collapseBuySectionsForSummary(sections);
  const sec = collapsed.find((s) => s.key === key);
  if (!sec || sec.indicator_status === "ERROR") {
    return null;
  }
  if (sec.count === null || sec.count === undefined) {
    return null;
  }
  return Math.max(0, Number(sec.count) || 0);
}

/** Compact count lines when no advisor action rows exist. */
export type TodaysSummaryResult = {
  lines: string[];
  allCountsZero: boolean;
  allCountsUnknown: boolean;
};

export function buildTodaysSummaryResult(
  sections: P85CollectorHomeRead["sections"],
): TodaysSummaryResult {
  const lines: string[] = [];
  let anyKnown = false;
  let allZero = true;
  for (const { key, label } of TODAY_SUMMARY_KEYS) {
    const count = sectionCountForSummary(sections, key);
    if (count === null) {
      continue;
    }
    anyKnown = true;
    if (count > 0) {
      allZero = false;
    }
    lines.push(`${label}: ${count}`);
  }
  if (!anyKnown) {
    return {
      lines: [],
      allCountsZero: false,
      allCountsUnknown: true,
    };
  }
  return {
    lines,
    allCountsZero: allZero,
    allCountsUnknown: false,
  };
}

export function buildTodaysSummaryLines(sections: P85CollectorHomeRead["sections"]): string[] {
  return buildTodaysSummaryResult(sections).lines;
}

/** @deprecated use buildTodaysSummaryLines */
export function buildTodaysActionsCompactSummary(sections: P85CollectorHomeRead["sections"]): string {
  return buildTodaysSummaryLines(sections).join(" · ");
}

export function homeHasSectionItemsReady(sections: P85CollectorHomeRead["sections"]): boolean {
  return sections.some(
    (s) => s.key !== "discovery_alerts" && s.indicator_status === "HAS_ITEMS",
  );
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
  buy.title = formatSectionTitleWithCount(SECTION_LABELS.buy_alerts, mergedRaw);
  buy.indicatorText = indicator.text;
  buy.indicatorShowCheck = indicator.showCheck;
  buy.indicatorTone = indicator.tone;

  const launcher = SECTION_SKIPPED_LAUNCHER.buy_alerts;
  if (!buy.showItems) {
    buy.body = launcher.body;
    const hasOpps =
      (mergedRaw.count ?? 0) > 0 ||
      mergedRaw.has_items === true ||
      mergedRaw.indicator_status === "HAS_ITEMS";
    if (hasOpps) {
      buy.actionLabel = "Open Marketplace Command Center";
      buy.actionTo = "/marketplace-command-center";
    } else {
      buy.actionLabel = launcher.button;
      buy.actionTo = launcher.to;
    }
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
  const baseTitle = SECTION_LABELS[sec.key] ?? sec.title;
  const title = formatSectionTitleWithCount(baseTitle, sec);
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
    let actionLabel = fallback.button;
    let actionTo = fallback.to;
    if (sec.key === "sell_alerts") {
      const hasOpps =
        sec.indicator_status === "HAS_ITEMS" ||
        (sec.count ?? 0) > 0 ||
        sec.has_items === true;
      if (hasOpps) {
        actionLabel = "Open Sell Command Center";
        actionTo = "/sell-command-center";
      }
    }
    let body = fallback.body;
    if (sec.key === "sell_alerts" && (sec.indicator_status === "HAS_ITEMS" || (sec.count ?? 0) > 0)) {
      body = "Review ranked sell actions, drafts, and listings from ComicOS.";
    }
    if (sec.key === "buy_alerts" && sec.items.length > 0) {
      const meta = sec.items[0] as { cross_market_count?: number; summary?: string };
      if (typeof meta.cross_market_count === "number" && meta.cross_market_count > 0) {
        body =
          meta.summary ??
          "Best marketplace deals identified across supported marketplaces.";
      }
    }
    return {
      ...base,
      items: [],
      body,
      actionLabel,
      actionTo,
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

function buildPortfolioHomeSection(): CollectorHomeDisplaySection {
  return {
    key: "portfolio",
    title: "Portfolio",
    items: [],
    body: "Track collection value, gains, and top books as you import.",
    actionLabel: "Open Portfolio",
    actionTo: "/dashboard",
    showItems: false,
    indicatorText: "Portfolio",
    indicatorShowCheck: false,
    indicatorTone: "static",
  };
}

function finalizeCollectorHomeSections(
  sections: CollectorHomeDisplaySection[],
): CollectorHomeDisplaySection[] {
  return [...sections, buildPortfolioHomeSection()]
    .map((section, index) => ({ section, index }))
    .sort(compareDisplaySections)
    .map(({ section }) => section);
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

  return finalizeCollectorHomeSections(
    prepared
      .filter((s) => s.key !== "discovery_alerts" && s.key !== "marketplace_deals")
      .map((section, index) => ({ section, index }))
      .sort(compareDisplaySections)
      .map(({ section }) => section),
  );
}

const STATIC_CARD_SORT_KEYS = new Set(["storage_issues"]);

function titleCountForSort(title: string): number {
  const match = title.match(/\((\d+)\)\s*$/);
  return match ? Number(match[1]) : -1;
}

function compareDisplaySections(
  a: { section: CollectorHomeDisplaySection; index: number },
  b: { section: CollectorHomeDisplaySection; index: number },
): number {
  if (a.section.key === "portfolio") {
    return -1;
  }
  if (b.section.key === "portfolio") {
    return 1;
  }
  const rankDiff = displaySectionSortRank(a.section) - displaySectionSortRank(b.section);
  if (rankDiff !== 0) {
    return rankDiff;
  }
  const countDiff = titleCountForSort(b.section.title) - titleCountForSort(a.section.title);
  if (countDiff !== 0) {
    return countDiff;
  }
  return a.index - b.index;
}

function displaySectionSortRank(section: CollectorHomeDisplaySection): number {
  if (section.key === "storage_issues") {
    return 50;
  }
  switch (section.indicatorTone) {
    case "has":
      return INDICATOR_SORT_RANK.HAS_ITEMS;
    case "stale":
      return INDICATOR_SORT_RANK.STALE;
    case "unknown":
    case "static":
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
    case "static":
      return "bg-blue-50 text-blue-900 ring-blue-200";
    case "unknown":
    default:
      return "bg-amber-50 text-amber-900 ring-amber-200";
  }
}
