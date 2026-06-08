import { MemoryRouter } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as apiClient from "../../api/client";
import { AutomationCenterPage } from "../AutomationCenterPage";
import {
  COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_COLLECTION,
  COLLECTOR_ADVISOR_NO_PLAN_MESSAGE,
} from "../collectorAdvisorPresentation";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ isOpsAdmin: false, isAuthenticated: true, isLoading: false }),
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
  afterEach(() => {
    cleanup();
  });

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
      status: "NO_SNAPSHOT",
      plan: null,
      message: COLLECTOR_ADVISOR_NO_PLAN_MESSAGE,
      generated_at: new Date().toISOString(),
    });
    render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(COLLECTOR_ADVISOR_NO_PLAN_MESSAGE)).toBeInTheDocument();
    expect(screen.queryByText(/batch job/i)).not.toBeInTheDocument();
  });

  it("renders EMPTY_NO_COLLECTION import guidance", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "EMPTY_NO_COLLECTION",
      plan: { ...plan, buy_actions: [], todays_actions: [], total_actions: 0 },
      message: COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_COLLECTION,
      generated_at: new Date().toISOString(),
    });
    render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("collector-advisor-status-banner")).toHaveTextContent(
      COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_COLLECTION,
    );
    expect(screen.getByRole("link", { name: /Import comics/i })).toBeInTheDocument();
  });
});
