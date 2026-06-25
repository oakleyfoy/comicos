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
      { label: "Collector Advisor", to: "/automation-center" },
      { label: "Today's Actions", to: "/daily-actions" },
      { label: "Command Center", to: "/collector-command-center" },
      { label: "Receive Comics", to: "/receiving" },
      { label: "Notifications", to: "/notifications" },
    ],
  },
  {
    id: "inventory",
    title: "Inventory",
    links: [
      { label: "Portfolio", to: "/dashboard", prominent: true },
      { label: "Collection insights", to: "/dashboard/collection", hiddenFromNav: true },
      { label: "Collection Gaps", to: "/collection-gaps" },
      { label: "Market & FMV", to: "/dashboard/market" },
      { label: "FMV Intelligence", to: "/fmv-intelligence" },
      { label: "Collection Valuation", to: "/collection-valuation-dashboard" },
      { label: "Key Issues", to: "/key-issues" },
      { label: "Want Lists", to: "/want-lists", hiddenFromNav: true },
    ],
  },
  {
    id: "acquire",
    title: "Add Comics",
    links: [
      { label: "Import retailer orders", to: "/connected-retailers/import", prominent: true },
      { label: "Phone Photo", to: "/add-comics/photo" },
      { label: "Import folder", to: "/add-comics/import-folder" },
      { label: "GPT Comic Read", to: "/add-comics/gpt-read" },
      { label: "Manual Entry", to: "/add-comics/manual" },
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
      { label: "Buy Opportunities", to: "/buy-opportunities" },
      { label: "Marketplace Monitoring", to: "/marketplace-monitoring" },
      { label: "Marketplace Command Center", to: "/marketplace-command-center" },
      { label: "Future Pull List", to: "/future-pull-list" },
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
      { label: "Sell Command Center", to: "/sell-command-center", prominent: true },
      { label: "Sell Queue", to: "/sell-queue", hiddenFromNav: true },
      { label: "Sell Candidates", to: "/sell-candidates" },
      { label: "Market Pricing", to: "/market-pricing" },
      { label: "Listing Drafts", to: "/listing-drafts" },
      { label: "Listing Management", to: "/listing-management" },
      { label: "Listings", to: "/listings", hiddenFromNav: true },
      { label: "Selling Analytics", to: "/selling-analytics", hiddenFromNav: true },
      { label: "Exit Dashboard", to: "/exit-dashboard", hiddenFromNav: true },
    ],
  },
  {
    id: "reports",
    title: "Reports",
    links: [
      { label: "Portfolio Analytics", to: "/portfolio-analytics", prominent: true },
      { label: "Recommendation Analytics", to: "/recommendation-analytics" },
      { label: "Discovery Dashboard", to: "/discovery-dashboard" },
      { label: "Discovery Opportunities", to: "/discovery-opportunities" },
      { label: "Discovery Watchlists", to: "/discovery-watchlists" },
      { label: "Discovery Alerts", to: "/discovery-alerts" },
      { label: "Release Lifecycle", to: "/release-lifecycle" },
      { label: "Discovery Analytics", to: "/discovery-analytics" },
      { label: "Daily Briefing", to: "/daily-briefing" },
      { label: "Weekly Briefing", to: "/weekly-briefing" },
      { label: "Platform Certification", to: "/platform-certification" },
      { label: "Production Readiness", to: "/production-readiness" },
      { label: "Discovery Feed", to: "/discovery-feed", hiddenFromNav: true },
      { label: "Release Intelligence", to: "/release-intelligence", hiddenFromNav: true },
      { label: "Future Releases", to: "/future-releases", hiddenFromNav: true },
    ],
  },
  {
    id: "settings",
    title: "Settings",
    links: [
      { label: "Collector Profile", to: "/collector-profile", prominent: true },
      { label: "Collector Budget", to: "/collector-budget" },
      { label: "Account & data", to: "/settings/account" },
      { label: "Data Protection", to: "/data-protection", hiddenFromNav: true },
      { label: "Workflow Health", to: "/workflow-health" },
    ],
  },
  {
    id: "catalog",
    title: "Catalog",
    links: [
      { label: "Master Universe", to: "/universe", prominent: true },
      { label: "Universe Tree", to: "/catalog-universe", prominent: true },
      { label: "GCD Import Dashboard", to: "/catalog/import", prominent: true },
      { label: "Placeholder Match Queue", to: "/catalog-universe/placeholders" },
    ],
  },
  {
    id: "legacy",
    title: "Legacy / Deprecated",
    links: [
      { label: "Gmail Imports", to: "/imports/email" },
      { label: "Email / Paste Import", to: "/imports/guided" },
      { label: "AI Import Drafts", to: "/imports" },
      { label: "Order Import (AI)", to: "/orders/import" },
      { label: "Gmail & Integrations", to: "/settings/integrations" },
    ],
  },
  /** Ops-only intake/scanner staging — last in sidebar until removed. */
  {
    id: "internal-tools",
    title: "Admin / Internal Tools",
    links: [
      { label: "Webcam Receiving", to: "/receiving/live", prominent: true, requiresOpsAdmin: true },
      { label: "Mobile Receiving", to: "/receiving/mobile", requiresOpsAdmin: true },
      { label: "Convention Scan", to: "/convention-scan", requiresOpsAdmin: true },
      { label: "Scan Intake", to: "/mobile-scan", requiresOpsAdmin: true },
      { label: "Mobile Intake", to: "/mobile-intake", requiresOpsAdmin: true },
      { label: "Scan Sessions", to: "/scan-sessions", requiresOpsAdmin: true },
      { label: "Scan Ingestion", to: "/scan-ingestion", requiresOpsAdmin: true },
      { label: "Scan OCR", to: "/scan-ocr", requiresOpsAdmin: true },
      { label: "Recognition Test", to: "/recognition-test", requiresOpsAdmin: true },
      { label: "Scanner Profiles", to: "/settings/scanner-profiles", requiresOpsAdmin: true },
      { label: "Operations Console", to: "/ops", requiresOpsAdmin: true },
    ],
  },
];

export const NAV_EXPANDED_STORAGE_KEY = "comic-os.nav.expanded-groups";

export const DEFAULT_EXPANDED_GROUP_IDS = ["home", "acquire"];

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
  if (pathname.startsWith("/discovery-") || pathname === "/release-lifecycle") {
    return "reports";
  }
  if (pathname === "/release-intelligence" || pathname === "/future-releases") {
    return "reports";
  }
  if (pathname === "/storage-box-contents" || pathname === "/storage-assignment") {
    return "storage";
  }
  if (pathname === "/purchase-budget") {
    return "settings";
  }
  if (
    pathname === "/universe" ||
    pathname === "/catalog-universe" ||
    pathname.startsWith("/catalog-universe/") ||
    pathname === "/catalog/import" ||
    pathname.startsWith("/catalog/import/")
  ) {
    return "catalog";
  }
  if (pathname.startsWith("/imports") ||
    pathname === "/orders/import" ||
    pathname === "/settings/integrations"
  ) {
    return "legacy";
  }
  if (pathname === "/orders/new" || pathname === "/connected-retailers/import") {
    return "acquire";
  }
  if (pathname.startsWith("/add-comics/")) {
    return "acquire";
  }
  if (pathname === "/mobile-scan" || pathname.startsWith("/mobile-scan/")) {
    return "acquire";
  }
  if (pathname === "/acquisitions" || pathname.startsWith("/acquisitions/")) {
    return null;
  }
  if (pathname.startsWith("/orders") || pathname.startsWith("/settings")) {
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
  if (pathname === "/receiving" || pathname.startsWith("/receiving/")) {
    return pathname === "/receiving" ? "home" : "internal-tools";
  }
  if (pathname === "/convention-scan" || pathname === "/mobile-intake") {
    return "internal-tools";
  }
  if (
    pathname === "/scan-sessions" ||
    pathname === "/scan-ingestion" ||
    pathname === "/scan-ocr" ||
    pathname === "/recognition-test" ||
    pathname.startsWith("/scan-") ||
    pathname === "/settings/scanner-profiles"
  ) {
    return "internal-tools";
  }
  if (pathname === "/ops" || pathname.startsWith("/ops/")) {
    return "internal-tools";
  }
  if (pathname === "/marketplace-command-center" || pathname.startsWith("/marketplace-command-center/")) {
    return "buy";
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
