import { describe, expect, it } from "vitest";

import type { P85CollectorHomeRead } from "../../api/client";
import {
  buildCollectorHomeHeaderSummary,
  buildDashboardStrip,
  buildTodaysSummaryResult,
  buildTodaysSummaryLines,
  COLLECTOR_HOME_READY_TAGLINE,
  homeHasSectionItemsReady,
  prepareCollectorHomeSections,
  sectionIndicatorDisplay,
  sortCollectorHomeSectionsForDisplay,
  SECTION_SKIPPED_LAUNCHER,
  STRIP_COLLECTION_VALUE_EMPTY,
} from "../collectorHomePresentation";

describe("collectorHomePresentation", () => {
  it("builds header without UNSET", () => {
    const home = {
      budget_status: { status: "SKIPPED", state: "UNSET", monthly_budget: null },
      portfolio_movement: { status: "SKIPPED", current_value: 0 },
    } as P85CollectorHomeRead;
    expect(buildCollectorHomeHeaderSummary(home)).toBe(COLLECTOR_HOME_READY_TAGLINE);
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
    expect(sectionIndicatorDisplay({ indicator_status: "ERROR", count: null } as never).text).toBe("No Alerts");
    expect(sectionIndicatorDisplay({ indicator_status: "UNKNOWN", count: null, key: "buy_alerts" } as never).text).toBe(
      "No Alerts",
    );
  });

  it("builds today summary without legacy fallback copy", () => {
    expect(buildTodaysSummaryResult([]).allCountsUnknown).toBe(true);
    expect(buildTodaysSummaryLines([])).toEqual([]);
    const result = buildTodaysSummaryResult([
      { key: "buy_alerts", indicator_status: "EMPTY", count: 0 } as never,
      { key: "sell_alerts", indicator_status: "EMPTY", count: 0 } as never,
      { key: "grade_alerts", indicator_status: "EMPTY", count: 0 } as never,
      { key: "future_pull_list", indicator_status: "EMPTY", count: 0 } as never,
    ]);
    expect(result.allCountsZero).toBe(true);
  });

  it("sorts HAS_ITEMS sections before EMPTY and puts Portfolio first", () => {
    const prepared = prepareCollectorHomeSections([
      { key: "buy_alerts", title: "Buy", items: [], empty_hint: "", count: 0, indicator_status: "EMPTY", status: "SKIPPED", error: "" },
      { key: "sell_alerts", title: "Sell", items: [], empty_hint: "", count: 3, indicator_status: "HAS_ITEMS", status: "SKIPPED", error: "" },
      { key: "storage_issues", title: "Storage", items: [], empty_hint: "", count: 0, indicator_status: "UNKNOWN", status: "SKIPPED", error: "" },
    ]);
    expect(prepared[0].key).toBe("portfolio");
    expect(prepared.map((s) => s.key).indexOf("sell_alerts")).toBeLessThan(prepared.map((s) => s.key).indexOf("buy_alerts"));
  });

  it("builds four-column dashboard strip for new collectors", () => {
    const metrics = buildDashboardStrip({
      portfolio_movement: { status: "SKIPPED", current_value: 0 },
      sections: [
        {
          key: "sell_alerts",
          title: "Sell",
          items: [],
          empty_hint: "",
          count: 0,
          indicator_status: "EMPTY",
          status: "SKIPPED",
          error: "",
        },
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
          key: "grade_alerts",
          title: "Grade",
          items: [],
          empty_hint: "",
          count: 0,
          indicator_status: "EMPTY",
          status: "SKIPPED",
          error: "",
        },
        {
          key: "future_pull_list",
          title: "Future",
          items: [],
          empty_hint: "",
          count: 0,
          indicator_status: "EMPTY",
          status: "SKIPPED",
          error: "",
        },
      ],
    } as P85CollectorHomeRead);
    expect(metrics).toHaveLength(4);
    expect(metrics[0].value).toBe(STRIP_COLLECTION_VALUE_EMPTY);
    expect(metrics[1].value).toBe("0");
    expect(metrics[2].label).toBe("Open Opportunities");
    expect(metrics[2].value).toBe("0");
    expect(metrics[3].label).toBe("Potential Profit");
    expect(metrics[3].value).toBe("0");
  });

  it("formats potential profit from cached portfolio movement", () => {
    const metrics = buildDashboardStrip({
      portfolio_movement: { status: "OK", current_value: 500, unrealized_gain: 120 },
      sections: [],
    } as P85CollectorHomeRead);
    expect(metrics[0].value).toBe("$500");
    expect(metrics[3].value).toBe("$120");
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
