export type NavLinkItem = {
  label: string;
  to: string;
  /** Highlight as primary landing link */
  prominent?: boolean;
  /** Requires ops admin (unchanged access rules). */
  requiresOpsAdmin?: boolean;
};

export type NavGroup = {
  id: string;
  title: string;
  links: NavLinkItem[];
};

/** Routes referenced by nav — must exist in App.tsx route config. */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: "primary",
    title: "Primary",
    links: [
      { label: "Executive Dashboard", to: "/executive-dashboard", prominent: true },
      { label: "ComicOS Intelligence", to: "/comicos-intelligence", prominent: true },
      { label: "Portfolio Analytics", to: "/portfolio-analytics", prominent: true },
      { label: "Sell Intelligence", to: "/sell-intelligence", prominent: true },
      { label: "Collector Workspace", to: "/collector-workspace", prominent: true },
      { label: "Today's Actions", to: "/daily-actions" },
      { label: "Unified Intelligence", to: "/unified-intelligence" },
      { label: "Top Recommendations", to: "/cross-system-recommendations" },
    ],
  },
  {
    id: "collection",
    title: "Collection",
    links: [
      { label: "Inventory portfolio", to: "/dashboard", prominent: true },
      { label: "Collection insights", to: "/dashboard/collection" },
      { label: "Market & FMV", to: "/dashboard/market" },
      { label: "Grading ops", to: "/dashboard/grading" },
      { label: "Dealer & strategy", to: "/dashboard/dealer" },
      { label: "Want Lists", to: "/want-lists" },
      { label: "Collection Gaps", to: "/collection-gaps" },
      { label: "Collected Runs", to: "/collected-runs" },
      { label: "Next Issues", to: "/next-issues" },
      { label: "Future Releases", to: "/future-releases" },
      { label: "Future Release Actions", to: "/future-release-actions" },
      { label: "Key Issues", to: "/key-issues" },
      { label: "Collector Intelligence", to: "/intelligence" },
    ],
  },
  {
    id: "buy",
    title: "Buy / Preorder",
    links: [
      { label: "Pull Lists", to: "/pull-lists" },
      { label: "Pull List Decisions", to: "/pull-list-decisions" },
      { label: "FOC Dashboard", to: "/foc-dashboard" },
      { label: "Purchase Profile", to: "/purchase-profile" },
      { label: "Purchase Quantities", to: "/purchase-quantities" },
      { label: "Purchase Variants", to: "/purchase-variants" },
      { label: "Budget Allocation", to: "/purchase-budget" },
      { label: "Acquisition Opportunities", to: "/acquisition-opportunities" },
      { label: "Marketplace Acquisitions", to: "/marketplace-acquisitions" },
      { label: "Acquisition Dashboard", to: "/acquisition-dashboard" },
    ],
  },
  {
    id: "sell",
    title: "Sell / Exit",
    links: [
      { label: "Sell Candidates", to: "/sell-candidates" },
      { label: "Exit Candidates", to: "/exit-candidates" },
      { label: "Hold vs Sell", to: "/hold-sell" },
      { label: "Grade Before Sell", to: "/grade-before-sell" },
      { label: "Portfolio Rebalancing", to: "/portfolio-rebalancing" },
      { label: "Exit Dashboard", to: "/exit-dashboard" },
    ],
  },
  {
    id: "market",
    title: "Market / Releases",
    links: [
      { label: "Release Intelligence", to: "/release-intelligence" },
      { label: "Release Monitoring", to: "/release-monitoring" },
      { label: "FOC & Purchase Intel", to: "/foc-purchase-intelligence" },
      { label: "Release Analytics", to: "/release-intelligence-analytics" },
      { label: "Storage Locations", to: "/storage-locations" },
      { label: "Storage Assignment", to: "/storage-assignment" },
      { label: "Storage Dashboard", to: "/storage-dashboard" },
      { label: "Inventory Locator", to: "/inventory-locator" },
      { label: "Box Contents", to: "/storage-box-contents" },
      { label: "Storage Audit", to: "/storage-audit" },
      { label: "Storage Labels", to: "/storage-label-preview" },
      { label: "Storage Analytics", to: "/storage-analytics" },
      { label: "Release Platform", to: "/release-platform" },
      { label: "Release Watchlists", to: "/release-watchlists" },
      { label: "Release Imports", to: "/release-imports" },
      { label: "Lunar Feed", to: "/lunar-feed" },
      { label: "Industry Publishers", to: "/industry-publishers" },
      { label: "Industry Release Scanner", to: "/industry-release-scanner" },
      { label: "Industry Signals", to: "/industry-signals" },
      { label: "Industry Opportunities", to: "/industry-opportunities" },
      { label: "Recommendations V2", to: "/recommendations-v2" },
      { label: "Recommendation Feedback", to: "/recommendation-feedback" },
      { label: "Recommendation Analytics", to: "/recommendation-analytics" },
      { label: "Spec Intelligence", to: "/spec-intelligence" },
      { label: "Spec Inputs", to: "/spec-inputs" },
      { label: "Spec Baseline", to: "/spec-baseline" },
      { label: "AI Spec Evaluations", to: "/ai-spec-evaluations" },
      { label: "Top 20 Spec Picks", to: "/top-spec-picks" },
      { label: "Market & User Intelligence", to: "/market-user-intelligence" },
      { label: "Forecast Platform", to: "/forecast-platform" },
    ],
  },
  {
    id: "imports",
    title: "Imports / Data",
    links: [
      { label: "Orders", to: "/orders" },
      { label: "Imports", to: "/imports" },
      { label: "Email Imports", to: "/imports/email" },
      { label: "Import Order", to: "/orders/import" },
      { label: "Add Order", to: "/orders/new" },
      { label: "Scanner Presets", to: "/settings/scanner-profiles" },
      { label: "Data Protection", to: "/data-protection" },
    ],
  },
  {
    id: "operations",
    title: "Operations / Admin",
    links: [
      { label: "Operations Reliability", to: "/operations-reliability" },
      { label: "Production Readiness", to: "/production-readiness" },
      { label: "Integrations", to: "/settings/integrations" },
      { label: "Agent Dashboard", to: "/agent-dashboard" },
      { label: "Marketplace Dashboard", to: "/marketplace-dashboard" },
      { label: "Dealer Copilot", to: "/dealer-copilot" },
      { label: "Rec Intelligence Certification", to: "/recommendation-intelligence-certification" },
      { label: "Release Platform Certification", to: "/release-platform-certification" },
      { label: "Operations", to: "/ops", requiresOpsAdmin: true },
    ],
  },
  {
    id: "intelligence",
    title: "Intelligence",
    links: [
      { label: "Future Release Intelligence", to: "/future-release-dashboard" },
      { label: "Industry Scanner Dashboard", to: "/industry-scanner-dashboard" },
      { label: "Weekly Spec Dashboard", to: "/weekly-spec-dashboard" },
      { label: "Top 20 Spec Picks", to: "/top-spec-picks" },
    ],
  },
  {
    id: "grading",
    title: "Grading",
    links: [
      { label: "Condition Intelligence", to: "/condition-intelligence" },
      { label: "Grading Intelligence", to: "/grading-intelligence" },
      { label: "Grading Operations", to: "/grading-operations" },
      { label: "Grading Queue", to: "/grading-queue" },
      { label: "Submission Batches", to: "/grading-batches" },
      { label: "Grading Analytics", to: "/grading-analytics" },
      { label: "Grading Validation", to: "/grading-validation" },
      { label: "Grading Platform", to: "/grading-platform" },
    ],
  },
];

export const NAV_EXPANDED_STORAGE_KEY = "comic-os.nav.expanded-groups";

export const DEFAULT_EXPANDED_GROUP_IDS = ["primary"];

export function findGroupIdForPath(pathname: string): string | null {
  for (const group of NAV_GROUPS) {
    for (const link of group.links) {
      if (pathname === link.to || (link.to !== "/dashboard" && pathname.startsWith(`${link.to}/`))) {
        return group.id;
      }
    }
  }
  if (pathname.startsWith("/dashboard")) {
    return "collection";
  }
  if (pathname.startsWith("/orders")) {
    return "imports";
  }
  if (pathname.startsWith("/imports")) {
    return "imports";
  }
  if (pathname.startsWith("/settings")) {
    return "imports";
  }
  if (pathname.startsWith("/inventory")) {
    return "collection";
  }
  return null;
}

export function visibleNavGroups(isOpsAdmin: boolean): NavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    links: group.links.filter((link) => !link.requiresOpsAdmin || isOpsAdmin),
  })).filter((group) => group.links.length > 0);
}
