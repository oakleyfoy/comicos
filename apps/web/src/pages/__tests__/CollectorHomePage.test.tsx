import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { apiClient, type P85CollectorHomeRead } from "../../api/client";
import { CollectorHomePage } from "../CollectorHomePage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

function baseHome(overrides: Partial<P85CollectorHomeRead> = {}): P85CollectorHomeRead {
  return {
    headline: "Fast operational dashboard",
    todays_actions: [],
    sections: [
      {
        key: "buy_alerts",
        title: "Buy alerts",
        items: [],
        empty_hint: "Open Buy Opportunities for buy alerts.",
        count: 0,
        indicator_status: "EMPTY",
        status: "SKIPPED",
        error: "",
      },
      {
        key: "sell_alerts",
        title: "Sell alerts",
        items: [],
        empty_hint: "Open Sell Queue for sell recommendations.",
        count: 4,
        has_items: true,
        indicator_status: "HAS_ITEMS",
        freshness_label: "Updated today",
        status: "SKIPPED",
        error: "",
      },
      {
        key: "marketplace_deals",
        title: "Marketplace deals",
        items: [],
        empty_hint: "",
        count: 0,
        indicator_status: "EMPTY",
        status: "SKIPPED",
        error: "",
      },
      {
        key: "discovery_alerts",
        title: "Discovery alerts",
        items: [],
        empty_hint: "Open Discovery Dashboard for alerts.",
        count: 0,
        status: "SKIPPED",
        error: "",
      },
    ],
    budget_status: { status: "SKIPPED", state: "UNSET", monthly_budget: null },
    portfolio_movement: { status: "SKIPPED", current_value: 0 },
    generated_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("CollectorHomePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("shows collector-facing header and compact today summary", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Collector Home" })).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "Today's actions" })).toBeInTheDocument();
    expect(screen.queryByText(/Fast operational dashboard/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SKIPPED/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/UNSET/i)).not.toBeInTheDocument();
    expect(screen.queryByText("No high-priority actions today")).not.toBeInTheDocument();
    expect(screen.queryByText("Review dashboards")).not.toBeInTheDocument();
    expect(screen.getByTestId("collector-home-todays-summary")).toHaveTextContent(
      "Sell Opportunities has 4 opportunities ready for review.",
    );
    expect(screen.queryByText("Discovery alerts")).not.toBeInTheDocument();
    expect(screen.queryByText("Discovery Alerts")).not.toBeInTheDocument();
    expect(screen.getAllByText("Buy Opportunities")).toHaveLength(1);
    expect(screen.queryByText("Buy Deals")).not.toBeInTheDocument();
    expect(screen.queryByText("Marketplace Deals")).not.toBeInTheDocument();
    expect(screen.getByText("Sell Opportunities")).toBeInTheDocument();
    expect(screen.getByText("4 available")).toBeInTheDocument();
    expect(
      screen.getByText("Review undervalued comics and marketplace deals identified by ComicOS."),
    ).toBeInTheDocument();
  });

  it("shows renamed collector-facing cards and priority order", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(
      baseHome({
        sections: [
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
          {
            key: "foc_alerts",
            title: "FOC",
            items: [],
            empty_hint: "",
            count: 0,
            indicator_status: "EMPTY",
            status: "SKIPPED",
            error: "",
          },
          {
            key: "storage_issues",
            title: "Storage",
            items: [],
            empty_hint: "",
            count: 0,
            indicator_status: "UNKNOWN",
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
      }),
    );
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("FOC & Preorders")).toBeInTheDocument();
    });
    expect(screen.queryByText("FOC Watch")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Find a Book" })).toBeInTheDocument();
    expect(screen.queryByText("Storage Check")).not.toBeInTheDocument();
    expect(screen.getByText("Upcoming Releases")).toBeInTheDocument();
    expect(screen.queryByText("Upcoming Pull List")).not.toBeInTheDocument();
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((el) => el.textContent)
      .filter((t) => t && t !== "Today's actions");
    expect(headings[0]).toBe("Buy Opportunities");
    expect(screen.getByText("5 available")).toBeInTheDocument();
  });

  it("shows no-immediate-actions summary when nothing has items", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(
      baseHome({
        sections: [
          {
            key: "sell_alerts",
            title: "Sell alerts",
            items: [],
            empty_hint: "",
            count: 0,
            indicator_status: "EMPTY",
            status: "SKIPPED",
            error: "",
          },
        ],
      }),
    );
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("collector-home-todays-summary")).toHaveTextContent(
        "No immediate actions require attention.",
      );
    });
  });

  it("does not show legacy empty actions copy", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("collector-home-todays-summary")).toBeInTheDocument();
    });
    expect(screen.queryByText(/No actions queued yet/i)).not.toBeInTheDocument();
  });

  it("renders EMPTY indicator copy", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("No current alerts")).toBeInTheDocument();
    });
  });

  it("renders launcher buttons for skipped sell and buy sections", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Sell Opportunities" })).toBeInTheDocument();
    });
    const sellSection = screen.getByRole("heading", { name: "Sell Opportunities" }).closest("section");
    expect(sellSection).not.toBeNull();
    expect(within(sellSection!).getByRole("link", { name: "Review Sell Queue" })).toBeInTheDocument();
    const buySection = screen.getByRole("heading", { name: "Buy Opportunities" }).closest("section");
    expect(buySection).not.toBeNull();
    expect(within(buySection!).getByRole("link", { name: "Review Buy Opportunities" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Buy Deals" })).not.toBeInTheDocument();
  });

  it("keeps Today’s Actions outside the section grid and renders action items", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(
      baseHome({
        todays_actions: [
          {
            title: "Review sell candidate",
            action_type: "SELL",
            priority_score: 90,
            source: "daily_actions",
            action_url: "/sell-queue",
          },
        ],
      }),
    );
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Review sell candidate" })).toBeInTheDocument();
    });
    expect(screen.queryByTestId("collector-home-todays-summary")).not.toBeInTheDocument();
    expect(screen.queryByText("No high-priority actions today")).not.toBeInTheDocument();
    const grid = screen.getByTestId("collector-home-section-grid");
    expect(grid.className).toMatch(/grid-cols-1/);
    expect(grid.className).toMatch(/md:grid-cols-2/);
    const todaysHeading = screen.getByRole("heading", { name: "Today's actions" });
    expect(todaysHeading.closest("[data-testid='collector-home-section-grid']")).toBeNull();
  });
});
