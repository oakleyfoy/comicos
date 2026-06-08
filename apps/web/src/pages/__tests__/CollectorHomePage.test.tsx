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
    expect(screen.getByRole("heading", { name: "Today's Summary" })).toBeInTheDocument();
    expect(screen.queryByText("Open dashboards to review current opportunities.")).not.toBeInTheDocument();
    expect(screen.getByTestId("collector-home-todays-summary")).toHaveTextContent("Buy Opportunities: 0");
    expect(screen.getByTestId("collector-home-todays-summary")).toHaveTextContent("Sell Opportunities: 4");
    expect(screen.getByRole("heading", { name: "Sell Opportunities (4)" })).toBeInTheDocument();
    expect(screen.getByText("4 Available")).toBeInTheDocument();
    expect(
      screen.getByText("Review buy recommendations and marketplace opportunities."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("collector-home-dashboard-strip")).toBeInTheDocument();
    expect(screen.getAllByText("Not Available").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("No alerts currently require attention.")).not.toBeInTheDocument();
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
            count: 12,
            indicator_status: "HAS_ITEMS",
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
      expect(screen.getByRole("heading", { name: "Buy Opportunities (5)" })).toBeInTheDocument();
    });
    expect(screen.getByText("5 Available")).toBeInTheDocument();
    expect(screen.getByText("Search")).toBeInTheDocument();
    expect(screen.queryByText(/^Review$/)).not.toBeInTheDocument();
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((el) => el.textContent)
      .filter((t) => t && t !== "Today's Summary" && t !== "Collector Advisor");
    expect(headings[0]).toBe("Portfolio");
  });

  it("shows monitoring message when all summary counts are zero", async () => {
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
      }),
    );
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("collector-home-monitoring-message")).toHaveTextContent(
        "ComicOS is actively monitoring your collection",
      );
    });
  });

  it("renders EMPTY indicator copy", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getAllByText("No Alerts").length).toBeGreaterThan(0);
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
      expect(screen.getByRole("heading", { name: "Sell Opportunities (4)" })).toBeInTheDocument();
    });
    const buySection = screen.getByRole("heading", { name: "Buy Opportunities (0)" }).closest("section");
    expect(buySection).not.toBeNull();
    expect(within(buySection!).getByRole("link", { name: "Open Buy Opportunities" })).toBeInTheDocument();
  });

  it("shows advisor placeholder copy when plan not ready", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome({ advisor_plan_ready: false }));
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("collector-home-advisor-summary")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Your personalized daily action plan will appear here once advisor data has been generated/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("Advisor plan not generated yet.")).not.toBeInTheDocument();
  });

  it("shows Portfolio as first grid card", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTestId("collector-home-section-grid")).toBeInTheDocument();
    });
    const grid = screen.getByTestId("collector-home-section-grid");
    const firstCardHeading = within(grid).getAllByRole("heading", { level: 2 })[0];
    expect(firstCardHeading).toHaveTextContent("Portfolio");
  });

  it("shows Portfolio card with Portfolio badge", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Portfolio" })).toBeInTheDocument();
    });
    const portfolioSection = screen.getByRole("heading", { name: "Portfolio" }).closest("section");
    expect(portfolioSection).not.toBeNull();
    expect(within(portfolioSection!).getByRole("heading", { name: "Portfolio" })).toBeInTheDocument();
    const badge = within(portfolioSection!).getAllByText("Portfolio").find((el) => el.tagName === "SPAN");
    expect(badge).toBeDefined();
    expect(within(portfolioSection!).queryByText(/^Review$/)).not.toBeInTheDocument();
  });

  it("does not add API calls beyond getCollectorHome", async () => {
    const spy = vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Collector Home" })).toBeInTheDocument();
    });
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
