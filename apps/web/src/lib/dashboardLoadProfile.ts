import { apiClient, type InventoryQueryParams, type InventoryOwnershipNormalized, type InventoryValuationScope, type MarketFmvConfidenceBucket } from "../api/client";

/** Which dashboard route variant is mounted — controls API fan-out and visible sections. */
export type DashboardLoadProfile =
  | "portfolio"
  | "collection"
  | "market"
  | "grading"
  | "dealer"
  | "full";

export type DashboardPortfolioFilters = {
  publisher: string;
  ownershipIntelFilter: InventoryOwnershipNormalized | "";
  valuationScopeFilter: InventoryValuationScope | "";
  confidenceBucketFilter: MarketFmvConfidenceBucket | "";
};

export const DASHBOARD_HUB_LINKS: { profile: DashboardLoadProfile; label: string; to: string; blurb: string }[] = [
  {
    profile: "portfolio",
    label: "Inventory portfolio",
    to: "/dashboard",
    blurb: "Summary cards, receiving, and your inventory grid.",
  },
  {
    profile: "collection",
    label: "Collection insights",
    to: "/dashboard/collection",
    blurb: "Analytics, risks, timeline, duplicates, and run gaps.",
  },
  {
    profile: "market",
    label: "Market & FMV",
    to: "/dashboard/market",
    blurb: "Comps, FMV ledger, trends, and market intelligence.",
  },
  {
    profile: "grading",
    label: "Grading ops",
    to: "/dashboard/grading",
    blurb: "Grading dashboards, reports, and command-center feeds.",
  },
  {
    profile: "dealer",
    label: "Dealer & strategy",
    to: "/dashboard/dealer",
    blurb: "Listings, liquidity, dealer feeds, and portfolio strategy.",
  },
  {
    profile: "full",
    label: "Full workspace (legacy)",
    to: "/dashboard/full",
    blurb: "Everything on one page — slower; prefer split views above.",
  },
];

export function dashboardProfileMeta(profile: DashboardLoadProfile): { title: string; description: string } {
  switch (profile) {
    case "portfolio":
      return {
        title: "Inventory Portfolio",
        description: "Summary, receiving, and inventory — loads a small set of APIs for day-to-day use.",
      };
    case "collection":
      return {
        title: "Collection Insights",
        description: "Coverage, risks, timeline, duplicates, and series progress for your collection.",
      };
    case "market":
      return {
        title: "Market & FMV",
        description: "Comparable sales, FMV snapshots, trends, and market workbench panels.",
      };
    case "grading":
      return {
        title: "Grading Operations",
        description: "Grading candidate, ROI, spread, reconciliation, and dealer grading feeds.",
      };
    case "dealer":
      return {
        title: "Dealer & Strategy",
        description: "Listings, liquidity, sales ledger, dealer dashboard, and portfolio strategy.",
      };
    default:
      return {
        title: "Full Portfolio Workspace",
        description: "All dashboard panels on one scroll (heavy — use split dashboards when possible).",
      };
  }
}

export function dashboardLoadsMarketEffects(profile: DashboardLoadProfile): boolean {
  return profile === "market" || profile === "full";
}

export function dashboardLoadsDealerEffects(profile: DashboardLoadProfile): boolean {
  return profile === "dealer" || profile === "full";
}

export function dashboardLoadsGradingEffects(profile: DashboardLoadProfile): boolean {
  return profile === "grading" || profile === "full";
}

export function dashboardShowsPortfolioMetricCards(profile: DashboardLoadProfile): boolean {
  return profile === "portfolio" || profile === "full";
}

export function dashboardShowsDashboardHub(profile: DashboardLoadProfile): boolean {
  return false;
}

export function dashboardShowsPortfolioPerformance(profile: DashboardLoadProfile): boolean {
  return profile === "full";
}

export function dashboardShowsInventoryGrid(profile: DashboardLoadProfile): boolean {
  return profile === "portfolio" || profile === "full";
}

export function dashboardShowsCollectionPanels(profile: DashboardLoadProfile): boolean {
  return profile === "collection" || profile === "full";
}

export function dashboardShowsExtendedWorkbench(profile: DashboardLoadProfile): boolean {
  return profile === "market" || profile === "grading" || profile === "dealer" || profile === "full";
}

export function dashboardShowsAutomationScanCards(profile: DashboardLoadProfile): boolean {
  return profile === "full";
}

export function buildDashboardShellWidgetPromises(
  filters: DashboardPortfolioFilters,
  profile: DashboardLoadProfile,
): Record<string, Promise<unknown>> {
  const portfolioValueParams = {
    publisher: filters.publisher || undefined,
    ownership_state: filters.ownershipIntelFilter || undefined,
    valuation_scope: filters.valuationScopeFilter || undefined,
    confidence_bucket: filters.confidenceBucketFilter || undefined,
  };

  const widgets: Record<string, Promise<unknown>> = {};

  const needsSummary =
    profile === "portfolio" ||
    profile === "collection" ||
    profile === "market" ||
    profile === "grading" ||
    profile === "dealer" ||
    profile === "full";
  if (needsSummary) {
    widgets.inventorySummary = apiClient.getInventorySummary();
  }

  if (profile === "collection" || profile === "full") {
    if (profile === "full") {
      widgets.portfolioPerformance = apiClient.getPortfolioPerformance();
    }
    widgets.inventoryRisks = apiClient.getInventoryRisksSummary();
    widgets.inventoryAction = apiClient.getInventoryActionCenterSummary();
    widgets.orderArrival = apiClient.getOrderArrivalIntelligenceSummary();
    widgets.collectionTimeline = apiClient.getCollectionHistoricalTimeline({ sort: "desc", limit: 40 });
    widgets.duplicateOwnership = apiClient.getDuplicateOwnershipList();
    widgets.runDetection = apiClient.getRunDetectionList();
    widgets.collectionAnalyticsSummary = apiClient.getCollectionAnalyticsSummary();
    widgets.collectionAnalyticsPublishers = apiClient.getCollectionAnalyticsPublishers();
    widgets.collectionAnalyticsQuality = apiClient.getCollectionAnalyticsQuality();
    widgets.scanPipeline = apiClient.getScanPipelineDashboard();
    widgets.inventoryIntelSummary = apiClient.getInventoryIntelligenceSummary();
    widgets.inventoryIntelHealth = apiClient.getInventoryIntelligenceHealth();
  }

  return widgets;
}

/** Heavy portfolio panels — loaded after first paint so the grid and summary appear quickly. */
export function buildPortfolioDeferredWidgetPromises(
  filters: DashboardPortfolioFilters,
  profile: DashboardLoadProfile,
): Record<string, Promise<unknown>> {
  if (profile !== "portfolio" && profile !== "full") {
    return {};
  }
  const portfolioValueParams = {
    publisher: filters.publisher || undefined,
    ownership_state: filters.ownershipIntelFilter || undefined,
    valuation_scope: filters.valuationScopeFilter || undefined,
    confidence_bucket: filters.confidenceBucketFilter || undefined,
  };
  return {
    portfolioValue: apiClient.getPortfolioValueSummary(portfolioValueParams),
    physicalIntake: apiClient.getPhysicalIntakeSummary(),
    inventoryArrivalTracking: apiClient.getInventoryArrivalTracking({ not_released_limit: 40 }),
  };
}

export function buildInventoryListWidgetPromises(
  query: InventoryQueryParams,
  profile: DashboardLoadProfile,
): Record<string, Promise<unknown>> {
  if (!dashboardShowsInventoryGrid(profile)) {
    return {};
  }
  return { inventoryList: apiClient.getInventory(query) };
}

export function buildDashboardWidgetPromises(
  query: InventoryQueryParams,
  filters: DashboardPortfolioFilters,
  profile: DashboardLoadProfile,
): Record<string, Promise<unknown>> {
  return {
    ...buildDashboardShellWidgetPromises(filters, profile),
    ...buildInventoryListWidgetPromises(query, profile),
  };
}
