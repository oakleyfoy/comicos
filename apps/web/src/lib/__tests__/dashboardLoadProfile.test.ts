import { describe, expect, it } from "vitest";

import { buildDashboardWidgetPromises, type DashboardLoadProfile } from "../dashboardLoadProfile";

describe("buildDashboardWidgetPromises", () => {
  const filters = {
    publisher: "",
    ownershipIntelFilter: "" as const,
    valuationScopeFilter: "" as const,
    confidenceBucketFilter: "" as const,
  };
  const query = { page: 1, page_size: 25, sort_by: "purchase_date" as const, sort_dir: "asc" as const };

  it("portfolio profile requests only a small widget set", () => {
    const keys = Object.keys(buildDashboardWidgetPromises(query, filters, "portfolio")).sort();
    expect(keys).toEqual(["inventoryList", "inventorySummary", "physicalIntake", "portfolioValue"].sort());
  });

  it("collection profile adds analytics widgets but not market-only panels", () => {
    const keys = Object.keys(buildDashboardWidgetPromises(query, filters, "collection"));
    expect(keys).toContain("collectionAnalyticsSummary");
    expect(keys).toContain("inventoryIntelSummary");
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
