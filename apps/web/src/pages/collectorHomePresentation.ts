import type { P85CollectorHomeRead } from "../api/client";

export const COLLECTOR_HOME_TITLE = "Collector Home";

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
};

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

function sectionDisplay(sec: P85CollectorHomeRead["sections"][number]): CollectorHomeDisplaySection {
  const title = SECTION_LABELS[sec.key] ?? sec.title;
  const emptyAction = SECTION_EMPTY_ACTIONS[sec.key] ?? {
    label: "Learn more",
    to: "/discovery-dashboard",
  };
  const launcher = SECTION_SKIPPED_LAUNCHER[sec.key];
  const emptyMessage = SECTION_EMPTY_MESSAGES[sec.key] ?? "Nothing to show right now.";

  if (sec.status === "ERROR") {
    return {
      key: sec.key,
      title,
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
      key: sec.key,
      title,
      items: [],
      body: fallback.body,
      actionLabel: fallback.button,
      actionTo: fallback.to,
      showItems: false,
    };
  }

  const hasItems = sec.count > 0 && sec.items.length > 0;
  if (hasItems) {
    return {
      key: sec.key,
      title,
      items: sec.items,
      body: "",
      actionLabel: emptyAction.label,
      actionTo: emptyAction.to,
      showItems: true,
    };
  }

  return {
    key: sec.key,
    title,
    items: [],
    body: emptyMessage,
    actionLabel: emptyAction.label,
    actionTo: emptyAction.to,
    showItems: false,
  };
}

/** Merge discovery alerts into marketplace/buy display; hide discovery card. */
export function prepareCollectorHomeSections(
  sections: P85CollectorHomeRead["sections"],
): CollectorHomeDisplaySection[] {
  const discovery = sections.find((s) => s.key === "discovery_alerts");
  const rest = sections.filter((s) => s.key !== "discovery_alerts");
  const prepared = rest.map(sectionDisplay);

  if (discovery && discovery.items.length > 0) {
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

  return prepared;
}

export function itemLabel(item: Record<string, unknown>): string {
  const title = item.title ?? item.label;
  if (title !== undefined && title !== null && String(title).trim()) {
    return String(title);
  }
  return "Item";
}
