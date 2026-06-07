import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { AutomationCenterPage } from "../AutomationCenterPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const plan: clientModule.P90CollectorAdvisorSnapshotRead = {
  id: 1,
  snapshot_date: "2026-06-07",
  buy_actions: [
    {
      category: "BUY",
      comic: "Battle Beast #2",
      reason: "Strong discount",
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
      detail: "Strong discount",
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
    portfolio_score: 42,
  },
  created_at: "2026-06-07T12:00:00Z",
};

describe("CollectorAdvisorPage", () => {
  it("renders dashboard and impact", async () => {
    vi.spyOn(clientModule.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan,
      generated_at: "2026-06-07T12:00:00Z",
    });
    render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Collector Advisor")).toBeInTheDocument();
    expect(screen.getAllByText("Buy Battle Beast #2").length).toBeGreaterThan(0);
    expect(screen.getByText("Portfolio impact")).toBeInTheDocument();
    expect(screen.getByText(/HIGH confidence · priority 88/)).toBeInTheDocument();
  });

  it("renders empty state", async () => {
    vi.spyOn(clientModule.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "EMPTY",
      plan: null,
      generated_at: "2026-06-07T12:00:00Z",
    });
    render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("No advisor plan yet")).toBeInTheDocument();
  });
});
