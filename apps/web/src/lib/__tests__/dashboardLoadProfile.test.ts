import { describe, expect, it } from "vitest";

import {
  buildDashboardWidgetPromises,
  buildDashboardShellWidgetPromises,
  buildPortfolioDeferredWidgetPromises,
  type DashboardLoadProfile,
} from "../dashboardLoadProfile";

describe("buildDashboardWidgetPromises", () => {
  const filters = {
    publisher: "",
    ownershipIntelFilter: "" as const,
    valuationScopeFilter: "" as const,
    confidenceBucketFilter: "" as const,
  };
  const query = { page: 1, page_size: 25, sort_by: "purchase_date" as const, sort_dir: "asc" as const };

  it("portfolio profile requests only a small widget set", () => {
    const shellKeys = Object.keys(buildDashboardShellWidgetPromises(filters, "portfolio")).sort();
    expect(shellKeys).toEqual(["inventorySummary"]);
    const deferredKeys = Object.keys(buildPortfolioDeferredWidgetPromises(filters, "portfolio")).sort();
    expect(deferredKeys).toEqual(
      ["inventoryArrivalTracking", "physicalIntake", "portfolioValue"].sort(),
    );
    const keys = Object.keys(buildDashboardWidgetPromises(query, filters, "portfolio")).sort();
    expect(keys).toEqual(
      ["inventoryArrivalTracking", "inventoryList", "inventorySummary", "physicalIntake", "portfolioValue"].sort(),
    );
  });

  it("collection profile adds analytics widgets without portfolio value batch", () => {
    const keys = Object.keys(buildDashboardWidgetPromises(query, filters, "collection"));
    expect(keys).toContain("collectionAnalyticsSummary");
    expect(keys).toContain("inventoryIntelSummary");
    expect(keys).not.toContain("portfolioValue");
    expect(keys).not.toContain("portfolioPerformance");
    expect(keys).not.toContain("inventoryList");
    expect(keys.length).toBeGreaterThan(6);
  });

  it("market profile loads summary only from widget batch", () => {
    const keys = Object.keys(buildDashboardWidgetPromises(query, filters, "market"));
    expect(keys).toEqual(["inventorySummary"]);
  });

  const emptyProfiles: DashboardLoadProfile[] = ["grading", "dealer"];
  it.each(emptyProfiles)("profile %s loads summary only from widget batch", (profile) => {
    expect(Object.keys(buildDashboardWidgetPromises(query, filters, profile))).toEqual(["inventorySummary"]);
  });
});
