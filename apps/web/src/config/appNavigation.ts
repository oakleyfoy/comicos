export type NavLinkItem = {
  label: string;
  to: string;
  prominent?: boolean;
  requiresOpsAdmin?: boolean;
  /** Hide from sidebar when route is not production-safe yet. */
  hiddenFromNav?: boolean;
};

export type NavGroup = {
  id: string;
  title: string;
  links: NavLinkItem[];
};

/** Session key for preserving sidebar scroll across route changes. */
export const NAV_SIDEBAR_SCROLL_KEY = "comicos.sidebar.scrollTop";

/** P85 workflow-oriented navigation (legacy phase pages live under logical groups). */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "home",
    title: "Home",
    links: [
      { label: "Collector Home", to: "/collector-home", prominent: true },
      { label: "Today's Actions", to: "/daily-actions" },
      { label: "Command Center", to: "/collector-command-center" },
      { label: "Notifications", to: "/notifications" },
    ],
  },
  {
    id: "buy",
    title: "Buy",
    links: [
      { label: "Pull Lists", to: "/pull-lists", prominent: true },
      { label: "FOC Dashboard", to: "/foc-dashboard" },
      { label: "Purchase Budget", to: "/purchase-budget", hiddenFromNav: true },
      { label: "Acquisition Opportunities", to: "/acquisition-opportunities", hiddenFromNav: true },
      { label: "Marketplace Opportunities", to: "/marketplace-opportunities" },
      { label: "Discovery Feed", to: "/discovery-feed", hiddenFromNav: true },
      { label: "Future Pull List", to: "/future-pull-list" },
    ],
  },
  {
    id: "inventory",
    title: "Inventory",
    links: [
      { label: "Portfolio", to: "/dashboard", prominent: true },
      { label: "Collection insights", to: "/dashboard/collection", hiddenFromNav: true },
      { label: "Gmail Imports", to: "/imports/email" },
      { label: "Order Import", to: "/orders/import" },
      { label: "Manual & AI Import", to: "/imports" },
      { label: "Collection Gaps", to: "/collection-gaps" },
      { label: "Market & FMV", to: "/dashboard/market" },
      { label: "Collection Valuation", to: "/collection-valuation-dashboard" },
      { label: "Key Issues", to: "/key-issues" },
      { label: "Want Lists", to: "/want-lists", hiddenFromNav: true },
    ],
  },
  {
    id: "storage",
    title: "Storage",
    links: [
      { label: "Storage Dashboard", to: "/storage-dashboard", prominent: true },
      { label: "Locations", to: "/storage-locations" },
      { label: "Assignment", to: "/storage-assignment", hiddenFromNav: true },
      { label: "Inventory Locator", to: "/inventory-locator" },
      { label: "Box Contents", to: "/storage-box-contents", hiddenFromNav: true },
      { label: "Storage Audit", to: "/storage-audit" },
    ],
  },
  {
    id: "grade",
    title: "Grade",
    links: [
      { label: "Grading Queue", to: "/grading-queue", prominent: true },
      { label: "Grading Intelligence", to: "/grading-intelligence" },
      { label: "Grading Operations", to: "/grading-operations", hiddenFromNav: true },
      { label: "Grade Before Sell", to: "/grade-before-sell" },
      { label: "Grading Platform", to: "/grading-platform", hiddenFromNav: true },
    ],
  },
  {
    id: "sell",
    title: "Sell",
    links: [
      { label: "Sell Queue", to: "/sell-queue", prominent: true },
      { label: "Sell Candidates", to: "/sell-candidates", hiddenFromNav: true },
      { label: "Listing Drafts", to: "/listing-drafts" },
      { label: "Listings", to: "/listings" },
      { label: "Selling Analytics", to: "/selling-analytics" },
      { label: "Exit Dashboard", to: "/exit-dashboard", hiddenFromNav: true },
    ],
  },
  {
    id: "discovery",
    title: "Discovery",
    links: [
      { label: "Discovery Dashboard", to: "/discovery-dashboard", prominent: true },
      { label: "Opportunities", to: "/discovery-opportunities" },
      { label: "Watchlists", to: "/discovery-watchlists" },
      { label: "Discovery Alerts", to: "/discovery-alerts" },
      { label: "Release Intelligence", to: "/release-intelligence", hiddenFromNav: true },
      { label: "Future Releases", to: "/future-releases", hiddenFromNav: true },
    ],
  },
  {
    id: "mobile",
    title: "Mobile",
    links: [
      { label: "Mobile Scanning", to: "/mobile-scan", prominent: true },
      { label: "Mobile Operations", to: "/mobile-operations" },
      { label: "Collector Assistant", to: "/collector-assistant" },
      { label: "Convention Mode", to: "/convention-mode", hiddenFromNav: true },
      { label: "Quick Sales", to: "/quick-sales", hiddenFromNav: true },
    ],
  },
  {
    id: "reports",
    title: "Reports",
    links: [
      { label: "Portfolio Analytics", to: "/portfolio-analytics", prominent: true },
      { label: "Recommendation Analytics", to: "/recommendation-analytics" },
      { label: "Discovery Analytics", to: "/discovery-analytics" },
      { label: "Daily Briefing", to: "/daily-briefing" },
      { label: "Weekly Briefing", to: "/weekly-briefing" },
      { label: "Platform Certification", to: "/platform-certification" },
      { label: "Production Readiness", to: "/production-readiness" },
    ],
  },
  {
    id: "settings",
    title: "Settings",
    links: [
      { label: "Collector Profile", to: "/collector-profile", prominent: true },
      { label: "Collector Budget", to: "/collector-budget" },
      { label: "Integrations", to: "/settings/integrations", hiddenFromNav: true },
      { label: "Data Protection", to: "/data-protection", hiddenFromNav: true },
      { label: "Operations", to: "/ops", requiresOpsAdmin: true },
      { label: "Workflow Health", to: "/workflow-health" },
    ],
  },
];

export const NAV_EXPANDED_STORAGE_KEY = "comic-os.nav.expanded-groups";

export const DEFAULT_EXPANDED_GROUP_IDS = ["home"];

export function findGroupIdForPath(pathname: string): string | null {
  for (const group of NAV_GROUPS) {
    for (const link of group.links) {
      if (pathname === link.to || (link.to !== "/dashboard" && pathname.startsWith(`${link.to}/`))) {
        return group.id;
      }
    }
  }
  if (pathname.startsWith("/dashboard")) {
    return "inventory";
  }
  if (pathname === "/collection-gaps") {
    return "inventory";
  }
  if (pathname === "/grading-platform" || pathname === "/grading-analytics") {
    return "grade";
  }
  if (pathname === "/release-intelligence") {
    return "discovery";
  }
  if (pathname === "/storage-box-contents" || pathname === "/storage-assignment") {
    return "storage";
  }
  if (pathname === "/purchase-budget") {
    return "settings";
  }
  if (pathname.startsWith("/orders") || pathname.startsWith("/imports") || pathname.startsWith("/settings")) {
    return "settings";
  }
  if (pathname.startsWith("/inventory")) {
    return "inventory";
  }
  if (pathname === "/executive-dashboard") {
    return "home";
  }
  if (pathname.startsWith("/collector-") || pathname === "/daily-actions") {
    return "home";
  }
  if (pathname === "/operations-reliability") {
    return "reports";
  }
  return null;
}

export function visibleNavGroups(isOpsAdmin: boolean): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    links: group.links.filter(
      (link) => !link.hiddenFromNav && (!link.requiresOpsAdmin || isOpsAdmin),
    ),
  })).filter((group) => group.links.length > 0);
}
