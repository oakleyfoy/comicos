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
        empty_hint: "Open Marketplace Opportunities for buy alerts.",
        count: 0,
        status: "SKIPPED",
        error: "",
      },
      {
        key: "sell_alerts",
        title: "Sell alerts",
        items: [],
        empty_hint: "Open Sell Queue for sell recommendations.",
        count: 0,
        status: "SKIPPED",
        error: "",
      },
      {
        key: "marketplace_deals",
        title: "Marketplace deals",
        items: [],
        empty_hint: "Open Marketplace Opportunities for deals.",
        count: 0,
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

  it("shows collector-facing header and empty states", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Collector Home" })).toBeInTheDocument();
    });
    expect(screen.queryByText(/Fast operational dashboard/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/SKIPPED/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/UNSET/i)).not.toBeInTheDocument();
    expect(screen.getByText("No high-priority actions today")).toBeInTheDocument();
    expect(screen.queryByText("Discovery alerts")).not.toBeInTheDocument();
    expect(screen.queryByText("Discovery Alerts")).not.toBeInTheDocument();
    expect(screen.getByText("Marketplace Deals")).toBeInTheDocument();
    expect(
      screen.getByText("Open marketplace acquisition tools to review deal opportunities."),
    ).toBeInTheDocument();
  });

  it("does not show legacy empty actions copy", async () => {
    vi.spyOn(apiClient, "getCollectorHome").mockResolvedValue(baseHome());
    render(
      <MemoryRouter>
        <CollectorHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("No high-priority actions today")).toBeInTheDocument();
    });
    expect(screen.queryByText(/No actions queued yet/i)).not.toBeInTheDocument();
  });

  it("renders launcher buttons for skipped sell and marketplace sections", async () => {
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
    const dealsSection = screen.getByRole("heading", { name: "Marketplace Deals" }).closest("section");
    expect(within(dealsSection!).getByRole("link", { name: "Review Marketplace Deals" })).toBeInTheDocument();
  });
});
