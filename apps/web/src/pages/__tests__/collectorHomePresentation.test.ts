import { describe, expect, it } from "vitest";

import type { P85CollectorHomeRead } from "../../api/client";
import {
  buildCollectorHomeHeaderSummary,
  buildDashboardStrip,
  buildTodaysSummaryResult,
  buildTodaysSummaryLines,
  homeHasSectionItemsReady,
  prepareCollectorHomeSections,
  sectionIndicatorDisplay,
  sortCollectorHomeSectionsForDisplay,
  SECTION_SKIPPED_LAUNCHER,
} from "../collectorHomePresentation";

describe("collectorHomePresentation", () => {
  it("builds header without UNSET", () => {
    const home = {
      budget_status: { status: "SKIPPED", state: "UNSET", monthly_budget: null },
      portfolio_movement: { status: "SKIPPED", current_value: 0 },
    } as P85CollectorHomeRead;
    expect(buildCollectorHomeHeaderSummary(home)).toBe("Your daily comic collecting launch pad.");
  });

  it("merges discovery into buy opportunities and drops discovery card", () => {
    const sections = prepareCollectorHomeSections([
      {
        key: "buy_alerts",
        title: "Buy",
        items: [{ title: "Deal A" }],
        empty_hint: "",
        count: 1,
        status: "OK",
        error: "",
      },
      {
        key: "discovery_alerts",
        title: "Discovery alerts",
        items: [{ title: "Discovery B" }],
        empty_hint: "",
        count: 1,
        status: "OK",
        error: "",
      },
    ]);
    expect(sections.some((s) => s.key === "discovery_alerts")).toBe(false);
    const buy = sections.find((s) => s.key === "buy_alerts");
    expect(buy?.items).toHaveLength(2);
    expect(buy?.title).toBe("Buy Opportunities (1)");
  });

  it("collapses buy_alerts and marketplace_deals into one card with strongest indicator", () => {
    const sections = prepareCollectorHomeSections([
      {
        key: "buy_alerts",
        title: "Buy",
        items: [],
        empty_hint: "",
        count: 0,
        indicator_status: "EMPTY",
        status: "SKIPPED",
        error: "",
      },
      {
        key: "marketplace_deals",
        title: "Deals",
        items: [],
        empty_hint: "",
        count: 5,
        indicator_status: "HAS_ITEMS",
        status: "SKIPPED",
        error: "",
      },
    ]);
    expect(sections.filter((s) => s.key === "buy_alerts")).toHaveLength(1);
    expect(sections.find((s) => s.key === "buy_alerts")?.indicatorText).toBe("5 Available");
    expect(sections.find((s) => s.key === "buy_alerts")?.title).toBe("Buy Opportunities (5)");
    expect(sections.find((s) => s.key === "buy_alerts")?.actionLabel).toBe("Open Marketplace Command Center");
  });

  it("maps SKIPPED sections to launcher copy without SKIPPED in output", () => {
    const sections = prepareCollectorHomeSections([
      {
        key: "sell_alerts",
        title: "Sell alerts",
        items: [],
        empty_hint: "",
        count: 0,
        status: "SKIPPED",
        error: "Temporarily skipped on Collector Home",
      },
    ]);
    expect(sections.some((s) => s.key === "portfolio")).toBe(true);
    const sell = sections.find((s) => s.key === "sell_alerts");
    expect(sell?.body).toBe(SECTION_SKIPPED_LAUNCHER.sell_alerts.body);
    expect(sell?.actionLabel).toBe("Open Sell Command Center");
  });

  it("maps indicator_status to user-facing labels", () => {
    expect(sectionIndicatorDisplay({ indicator_status: "HAS_ITEMS", count: 3 } as never).text).toBe(
      "3 Available",
    );
    expect(sectionIndicatorDisplay({ indicator_status: "EMPTY", count: 0 } as never).text).toBe("No Alerts");
    expect(sectionIndicatorDisplay({ indicator_status: "UNKNOWN", count: null, key: "storage_issues" } as never).text).toBe(
      "Search",
    );
    expect(sectionIndicatorDisplay({ indicator_status: "UNKNOWN", count: null, key: "foc_alerts" } as never).text).toBe(
      "FOC",
    );
    expect(sectionIndicatorDisplay({ indicator_status: "ERROR", count: null } as never).text).toBe("Unavailable");
  });

  it("builds today summary without dashboard fallback copy", () => {
    expect(buildTodaysSummaryLines([])).toEqual(["No alerts currently require attention."]);
    const result = buildTodaysSummaryResult([
      { key: "buy_alerts", indicator_status: "EMPTY", count: 0 } as never,
      { key: "sell_alerts", indicator_status: "EMPTY", count: 0 } as never,
      { key: "grade_alerts", indicator_status: "EMPTY", count: 0 } as never,
      { key: "future_pull_list", indicator_status: "EMPTY", count: 0 } as never,
    ]);
    expect(result.allCountsZero).toBe(true);
  });

  it("sorts HAS_ITEMS sections before EMPTY and static cards last", () => {
    const prepared = prepareCollectorHomeSections([
      { key: "buy_alerts", title: "Buy", items: [], empty_hint: "", count: 0, indicator_status: "EMPTY", status: "SKIPPED", error: "" },
      { key: "sell_alerts", title: "Sell", items: [], empty_hint: "", count: 3, indicator_status: "HAS_ITEMS", status: "SKIPPED", error: "" },
      { key: "storage_issues", title: "Storage", items: [], empty_hint: "", count: 0, indicator_status: "UNKNOWN", status: "SKIPPED", error: "" },
    ]);
    const keys = prepared.map((s) => s.key);
    expect(keys.indexOf("sell_alerts")).toBeLessThan(keys.indexOf("buy_alerts"));
    expect(keys.indexOf("portfolio")).toBeGreaterThan(keys.indexOf("sell_alerts"));
  });

  it("builds four-column dashboard strip with placeholders", () => {
    const metrics = buildDashboardStrip({
      portfolio_movement: { status: "OK", current_value: 1200 },
      sections: [
        {
          key: "listing_management",
          title: "Listings",
          items: [{ active_listings: 3 }],
          empty_hint: "",
          count: 3,
          status: "SKIPPED",
          error: "",
        },
        {
          key: "sell_alerts",
          title: "Sell",
          items: [],
          empty_hint: "",
          count: 2,
          indicator_status: "HAS_ITEMS",
          status: "SKIPPED",
          error: "",
        },
      ],
    } as P85CollectorHomeRead);
    expect(metrics).toHaveLength(4);
    expect(metrics[0]).toEqual({ label: "Collection Value", value: "$1,200" });
    expect(metrics[2]).toEqual({ label: "Active Listings", value: "3" });
    expect(metrics[3].label).toBe("Open Alerts");
  });

  it("detects sections with HAS_ITEMS for optional today hint", () => {
    expect(
      homeHasSectionItemsReady([{ key: "sell_alerts", indicator_status: "HAS_ITEMS" } as never]),
    ).toBe(true);
  });

  it("sorts HAS_ITEMS sections before EMPTY while preserving order within rank", () => {
    const sorted = sortCollectorHomeSectionsForDisplay([
      { key: "buy_alerts", indicator_status: "EMPTY" } as never,
      { key: "marketplace_deals", indicator_status: "HAS_ITEMS" } as never,
      { key: "sell_alerts", indicator_status: "HAS_ITEMS" } as never,
      { key: "grade_alerts", indicator_status: "UNKNOWN" } as never,
    ]);
    expect(sorted.map((s) => s.key)).toEqual([
      "marketplace_deals",
      "sell_alerts",
      "grade_alerts",
      "buy_alerts",
    ]);
  });
});
