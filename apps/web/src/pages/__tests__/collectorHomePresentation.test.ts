import { describe, expect, it } from "vitest";

import type { P85CollectorHomeRead } from "../../api/client";
import {
  buildCollectorHomeHeaderSummary,
  buildTodaysActionsCompactSummary,
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
    expect(buildCollectorHomeHeaderSummary(home)).toBe("Your daily comic collecting command center");
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
    expect(buy?.title).toBe("Buy Opportunities");
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
    expect(sections.some((s) => s.key === "marketplace_deals")).toBe(false);
    expect(sections.find((s) => s.key === "buy_alerts")?.indicatorText).toBe("5 available");
    expect(sections.find((s) => s.key === "buy_alerts")?.actionLabel).toBe("Review Buy Opportunities");
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
    expect(sections).toHaveLength(1);
    expect(sections[0].body).toBe(SECTION_SKIPPED_LAUNCHER.sell_alerts.body);
    expect(sections[0].actionLabel).toBe("Review Sell Queue");
    expect(JSON.stringify(sections[0])).not.toMatch(/SKIPPED/i);
  });

  it("maps indicator_status to user-facing labels", () => {
    expect(sectionIndicatorDisplay({ indicator_status: "HAS_ITEMS", count: 3 } as never).text).toBe("3 available");
    expect(sectionIndicatorDisplay({ indicator_status: "EMPTY", count: 0 } as never).text).toBe("No current alerts");
    expect(sectionIndicatorDisplay({ indicator_status: "UNKNOWN", count: null } as never).text).toBe("Open to review");
    expect(sectionIndicatorDisplay({ indicator_status: "HAS_ITEMS", count: 3 } as never).showCheck).toBe(true);
  });

  it("detects sections with HAS_ITEMS for optional today hint", () => {
    expect(
      homeHasSectionItemsReady([{ key: "sell_alerts", indicator_status: "HAS_ITEMS" } as never]),
    ).toBe(true);
  });

  it("builds compact today summary from section indicators", () => {
    expect(buildTodaysActionsCompactSummary([])).toBe("No immediate actions require attention.");
    expect(
      buildTodaysActionsCompactSummary([
        { key: "marketplace_deals", indicator_status: "HAS_ITEMS", count: 5 } as never,
      ]),
    ).toBe("Buy Opportunities has 5 opportunities ready for review.");
    expect(
      buildTodaysActionsCompactSummary([
        { key: "marketplace_deals", indicator_status: "HAS_ITEMS", count: 5 } as never,
        { key: "sell_alerts", indicator_status: "HAS_ITEMS", count: 2 } as never,
      ]),
    ).toBe("5 buy opportunities and 2 sell opportunities are ready for review.");
    expect(
      buildTodaysActionsCompactSummary([
        { key: "sell_alerts", indicator_status: "HAS_ITEMS", count: null } as never,
      ]),
    ).toBe("Some dashboards have items ready for review.");
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

  it("dedupes buy sections in today summary when both report HAS_ITEMS", () => {
    expect(
      buildTodaysActionsCompactSummary([
        { key: "buy_alerts", indicator_status: "HAS_ITEMS", count: 2 } as never,
        { key: "marketplace_deals", indicator_status: "HAS_ITEMS", count: 5 } as never,
      ]),
    ).toBe("Buy Opportunities has 5 opportunities ready for review.");
  });

  it("uses collector-facing section labels", () => {
    const prepared = prepareCollectorHomeSections([
      { key: "foc_alerts", title: "FOC alerts", items: [], empty_hint: "", status: "SKIPPED", error: "" },
      { key: "storage_issues", title: "Storage", items: [], empty_hint: "", status: "SKIPPED", error: "" },
      { key: "future_pull_list", title: "Future", items: [], empty_hint: "", status: "SKIPPED", error: "" },
    ]);
    expect(prepared.map((s) => s.title)).toEqual(["FOC & Preorders", "Find a Book", "Upcoming Releases"]);
  });
});
