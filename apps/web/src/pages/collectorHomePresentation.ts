import type { P85CollectorHomeRead } from "../api/client";

export const COLLECTOR_HOME_TITLE = "Collector Home";

export type SectionIndicatorStatus = "HAS_ITEMS" | "EMPTY" | "STALE" | "UNKNOWN" | "ERROR";

export const SECTION_LABELS: Record<string, string> = {
  buy_alerts: "Buy Opportunities",
  sell_alerts: "Sell Opportunities",
  grade_alerts: "Grade Candidates",
  foc_alerts: "FOC Watch",
  storage_issues: "Storage Check",
  marketplace_deals: "Marketplace Deals",
  future_pull_list: "Upcoming Pull List",
};

export const SECTION_EMPTY_MESSAGES: Record<string, string> = {
  buy_alerts: "No buy alerts right now",
  sell_alerts: "No sell alerts right now",
  grade_alerts: "No grade candidates right now",
  storage_issues: "No storage issues found",
  marketplace_deals: "No marketplace deal alerts right now",
  future_pull_list: "No upcoming release alerts right now",
  foc_alerts: "No FOC alerts available yet",
};

/** Friendly copy when backend marks section SKIPPED (full data on dedicated page). */
export const SECTION_SKIPPED_LAUNCHER: Record<
  string,
  { body: string; button: string; to: string }
> = {
  buy_alerts: {
    body: "Open the buy dashboard to review current recommendations.",
    button: "Review Buy Opportunities",
    to: "/marketplace-opportunities",
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
    body: "Open the FOC dashboard to review this week's preorder decisions.",
    button: "Review FOC Watch",
    to: "/foc-dashboard",
  },
  storage_issues: {
    body: "Open storage tools to review boxes, locations, and organization issues.",
    button: "Review Storage",
    to: "/storage-dashboard",
  },
  marketplace_deals: {
    body: "Open marketplace acquisition tools to review deal opportunities.",
    button: "Review Marketplace Deals",
    to: "/marketplace-opportunities",
  },
  future_pull_list: {
    body: "Open upcoming releases to review future books tied to your collection.",
    button: "Review Upcoming Releases",
    to: "/future-pull-list",
  },
};

/** Links when section is OK but empty (items loaded, none to show). */
export const SECTION_EMPTY_ACTIONS: Record<string, { label: string; to: string }> = {
  buy_alerts: { label: "Review Buy Opportunities", to: "/marketplace-opportunities" },
  sell_alerts: { label: "Review Sell Queue", to: "/sell-queue" },
  grade_alerts: { label: "Review Grade Candidates", to: "/grade-before-sell" },
  foc_alerts: { label: "Review FOC Watch", to: "/foc-dashboard" },
  storage_issues: { label: "Review Storage", to: "/storage-dashboard" },
  marketplace_deals: { label: "Review Marketplace Deals", to: "/marketplace-opportunities" },
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
  const actionable = sections.filter((s) => s.key !== "discovery_alerts" && s.indicator_status === "HAS_ITEMS");
  if (actionable.length === 0) {
    return "No immediate actions require attention.";
  }
  const hasNullCount = actionable.some((s) => s.count === null || s.count === undefined);
  if (hasNullCount) {
    return "Some dashboards have items ready for review.";
  }
  const totalCount = actionable.reduce((sum, s) => sum + Math.max(0, Number(s.count) || 0), 0);
  if (totalCount <= 0) {
    return "Some dashboards have items ready for review.";
  }
  return `Review ${totalCount} opportunities across ComicOS.`;
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

function mergeIndicatorPreferHasItems(
  target: CollectorHomeDisplaySection,
  source: P85CollectorHomeRead["sections"][number] | undefined,
): void {
  if (!source?.indicator_status) {
    return;
  }
  const sourceDisplay = sectionIndicatorDisplay(source);
  if (target.indicatorTone === "has") {
    return;
  }
  if (source.indicator_status === "HAS_ITEMS") {
    target.indicatorText = sourceDisplay.text;
    target.indicatorShowCheck = sourceDisplay.showCheck;
    target.indicatorTone = sourceDisplay.tone;
  }
}

/** Merge discovery alerts into marketplace/buy display; hide discovery card. */
export function prepareCollectorHomeSections(
  sections: P85CollectorHomeRead["sections"],
): CollectorHomeDisplaySection[] {
  const discovery = sections.find((s) => s.key === "discovery_alerts");
  const rest = sections.filter((s) => s.key !== "discovery_alerts");
  const prepared = rest.map(sectionDisplay);

  if (discovery) {
    if (discovery.items.length > 0) {
      const marketplace = prepared.find((s) => s.key === "marketplace_deals");
      if (marketplace) {
        marketplace.items = [...marketplace.items, ...discovery.items];
        marketplace.showItems = marketplace.items.length > 0;
        if (marketplace.showItems) {
          marketplace.body = "";
        }
      } else {
        const buy = prepared.find((s) => s.key === "buy_alerts");
        if (buy) {
          buy.items = [...buy.items, ...discovery.items];
          buy.showItems = buy.items.length > 0;
          if (buy.showItems) {
            buy.body = "";
          }
        }
      }
    }
    const marketplace = prepared.find((s) => s.key === "marketplace_deals");
    if (marketplace) {
      mergeIndicatorPreferHasItems(marketplace, discovery);
    }
  }

  return prepared;
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
      return "bg-slate-100 text-slate-600 ring-slate-200";
  }
}
