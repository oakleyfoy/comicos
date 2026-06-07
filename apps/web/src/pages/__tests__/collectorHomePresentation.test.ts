import { describe, expect, it } from "vitest";

import type { P85CollectorHomeRead } from "../../api/client";
import {
  buildCollectorHomeHeaderSummary,
  homeHasSectionItemsReady,
  prepareCollectorHomeSections,
  sectionIndicatorDisplay,
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

  it("merges discovery into marketplace and drops discovery card", () => {
    const sections = prepareCollectorHomeSections([
      {
        key: "marketplace_deals",
        title: "Marketplace deals",
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
    const deals = sections.find((s) => s.key === "marketplace_deals");
    expect(deals?.items).toHaveLength(2);
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
});
