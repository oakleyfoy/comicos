import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as apiClient from "../../api/client";
import { AutomationCenterPage } from "../AutomationCenterPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const plan: apiClient.P90CollectorAdvisorSnapshotRead = {
  id: 1,
  snapshot_date: "2026-06-07",
  buy_actions: [
    {
      category: "BUY",
      comic: "Battle Beast #2",
      reason: "Discount",
      confidence: "HIGH",
      priority_score: 88,
      potential_upside: 12,
      action_route: "/buy-opportunities",
      source_system: "P88",
      display_label: "Buy Battle Beast #2",
    },
  ],
  sell_actions: [],
  grade_actions: [],
  watch_actions: [],
  todays_actions: [
    {
      rank: 1,
      category: "BUY",
      title: "Buy Battle Beast #2",
      detail: "Strong buy opportunity",
      priority_score: 88,
      action_route: "/buy-opportunities",
    },
  ],
  recent_activity: [],
  market_alerts: [],
  total_actions: 1,
  portfolio_impact: {
    potential_profit: 0,
    potential_savings: 12,
    potential_value_gain: 0,
    portfolio_impact_total: 12,
    portfolio_score: 40,
  },
  created_at: new Date().toISOString(),
};

describe("AutomationCenterPage", () => {
  it("renders advisor sections and today's actions", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan,
      generated_at: new Date().toISOString(),
    });
    render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Collector Advisor", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Today's actions", level: 2 })).toBeInTheDocument();
    expect(screen.getAllByText("Buy Battle Beast #2").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Buy", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Portfolio impact", level: 2 })).toBeInTheDocument();
  });

  it("renders empty states", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "EMPTY",
      plan: null,
      generated_at: new Date().toISOString(),
    });
    render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("No advisor plan yet")).toBeInTheDocument();
  });
});
