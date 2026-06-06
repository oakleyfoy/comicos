export type NavLinkItem = {
  label: string;
  to: string;
  prominent?: boolean;
  requiresOpsAdmin?: boolean;
};

export type NavGroup = {
  id: string;
  title: string;
  links: NavLinkItem[];
};

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
      { label: "Daily Briefing", to: "/daily-briefing" },
      { label: "Workflow Health", to: "/workflow-health" },
      { label: "Executive Dashboard", to: "/executive-dashboard" },
    ],
  },
  {
    id: "buy",
    title: "Buy",
    links: [
      { label: "Pull Lists", to: "/pull-lists", prominent: true },
      { label: "FOC Dashboard", to: "/foc-dashboard" },
      { label: "Purchase Budget", to: "/purchase-budget" },
      { label: "Acquisition Opportunities", to: "/acquisition-opportunities" },
      { label: "Marketplace Opportunities", to: "/marketplace-opportunities" },
      { label: "Discovery Feed", to: "/discovery-feed" },
      { label: "Future Pull List", to: "/future-pull-list" },
    ],
  },
  {
    id: "inventory",
    title: "Inventory",
    links: [
      { label: "Portfolio", to: "/dashboard", prominent: true },
      { label: "Collection insights", to: "/dashboard/collection" },
      { label: "Market & FMV", to: "/dashboard/market" },
      { label: "Want Lists", to: "/want-lists" },
      { label: "Collection Gaps", to: "/collection-gaps" },
      { label: "Collection Valuation", to: "/collection-valuation-dashboard" },
      { label: "Key Issues", to: "/key-issues" },
    ],
  },
  {
    id: "storage",
    title: "Storage",
    links: [
      { label: "Storage Dashboard", to: "/storage-dashboard", prominent: true },
      { label: "Locations", to: "/storage-locations" },
      { label: "Assignment", to: "/storage-assignment" },
      { label: "Inventory Locator", to: "/inventory-locator" },
      { label: "Box Contents", to: "/storage-box-contents" },
      { label: "Storage Audit", to: "/storage-audit" },
    ],
  },
  {
    id: "grade",
    title: "Grade",
    links: [
      { label: "Grading Queue", to: "/grading-queue", prominent: true },
      { label: "Grading Intelligence", to: "/grading-intelligence" },
      { label: "Grading Operations", to: "/grading-operations" },
      { label: "Grade Before Sell", to: "/grade-before-sell" },
      { label: "Grading Platform", to: "/grading-platform" },
    ],
  },
  {
    id: "sell",
    title: "Sell",
    links: [
      { label: "Sell Queue", to: "/sell-queue", prominent: true },
      { label: "Sell Candidates", to: "/sell-candidates" },
      { label: "Listing Drafts", to: "/listing-drafts" },
      { label: "Listings", to: "/listings" },
      { label: "Selling Analytics", to: "/selling-analytics" },
      { label: "Exit Dashboard", to: "/exit-dashboard" },
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
      { label: "Release Intelligence", to: "/release-intelligence" },
      { label: "Future Releases", to: "/future-releases" },
    ],
  },
  {
    id: "mobile",
    title: "Mobile",
    links: [
      { label: "Mobile Scanning", to: "/mobile-scanning", prominent: true },
      { label: "Mobile Operations", to: "/mobile-operations" },
      { label: "Collector Assistant", to: "/collector-assistant" },
      { label: "Convention Mode", to: "/convention-mode" },
      { label: "Quick Sales", to: "/quick-sales" },
    ],
  },
  {
    id: "reports",
    title: "Reports",
    links: [
      { label: "Portfolio Analytics", to: "/portfolio-analytics", prominent: true },
      { label: "Recommendation Analytics", to: "/recommendation-analytics" },
      { label: "Discovery Analytics", to: "/discovery-analytics" },
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
      { label: "Integrations", to: "/settings/integrations" },
      { label: "Imports", to: "/imports" },
      { label: "Data Protection", to: "/data-protection" },
      { label: "Operations", to: "/ops", requiresOpsAdmin: true },
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
  if (pathname.startsWith("/orders") || pathname.startsWith("/imports") || pathname.startsWith("/settings")) {
    return "settings";
  }
  if (pathname.startsWith("/inventory")) {
    return "inventory";
  }
  if (pathname.startsWith("/collector-") || pathname === "/daily-actions") {
    return "home";
  }
  return null;
}

export function visibleNavGroups(isOpsAdmin: boolean): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    links: group.links.filter((link) => !link.requiresOpsAdmin || isOpsAdmin),
  })).filter((group) => group.links.length > 0);
}
