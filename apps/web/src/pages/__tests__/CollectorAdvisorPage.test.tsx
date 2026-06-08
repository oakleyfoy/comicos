import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { AutomationCenterPage } from "../AutomationCenterPage";
import {
  COLLECTOR_ADVISOR_GENERATE_CTA,
  COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_SIGNALS,
  COLLECTOR_ADVISOR_MESSAGE_GATHER_FAILED,
  COLLECTOR_ADVISOR_NO_PLAN_MESSAGE,
  COLLECTOR_ADVISOR_OPEN_PLAN_CTA,
  COLLECTOR_ADVISOR_SUBTITLE,
} from "../collectorAdvisorPresentation";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ isOpsAdmin: false, isAuthenticated: true, isLoading: false }),
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

const emptyPlan: clientModule.P90CollectorAdvisorSnapshotRead = {
  ...plan,
  buy_actions: [],
  todays_actions: [],
  total_actions: 0,
  portfolio_impact: {
    potential_profit: 0,
    potential_savings: 0,
    potential_value_gain: 0,
    portfolio_impact_total: 0,
    portfolio_score: 0,
  },
};

describe("CollectorAdvisorPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

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
    expect(screen.getByRole("link", { name: COLLECTOR_ADVISOR_OPEN_PLAN_CTA })).toBeInTheDocument();
  });

  it("renders NO_SNAPSHOT empty state", async () => {
    vi.spyOn(clientModule.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "NO_SNAPSHOT",
      plan: null,
      message: COLLECTOR_ADVISOR_NO_PLAN_MESSAGE,
      generated_at: "2026-06-07T12:00:00Z",
    });
    render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText(COLLECTOR_ADVISOR_SUBTITLE)).toBeInTheDocument();
    expect(screen.getByText(COLLECTOR_ADVISOR_NO_PLAN_MESSAGE)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: COLLECTOR_ADVISOR_GENERATE_CTA })).toBeInTheDocument();
    expect(screen.getByTestId("collector-advisor-empty")).toBeInTheDocument();
    expect(screen.queryByText(/batch job/i)).not.toBeInTheDocument();
  });

  it("renders EMPTY_NO_SIGNALS positive banner", async () => {
    vi.spyOn(clientModule.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "EMPTY_NO_SIGNALS",
      plan: emptyPlan,
      message: COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_SIGNALS,
      generated_at: "2026-06-07T12:00:00Z",
    });
    render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("collector-advisor-status-banner")).toHaveTextContent(
      COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_SIGNALS,
    );
    expect(screen.getByRole("heading", { name: "Today's actions" })).toBeInTheDocument();
  });

  it("renders EMPTY_GATHER_FAILED try again", async () => {
    vi.spyOn(clientModule.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "EMPTY_GATHER_FAILED",
      plan: emptyPlan,
      message: COLLECTOR_ADVISOR_MESSAGE_GATHER_FAILED,
      generated_at: "2026-06-07T12:00:00Z",
    });
    render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId("collector-advisor-status-banner")).toHaveTextContent(
      COLLECTOR_ADVISOR_MESSAGE_GATHER_FAILED,
    );
    expect(screen.getByRole("button", { name: "Try Again" })).toBeInTheDocument();
  });

  it("calls generate when empty CTA is clicked", async () => {
    vi.spyOn(clientModule.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "NO_SNAPSHOT",
      plan: null,
      generated_at: "2026-06-07T12:00:00Z",
    });
    const generate = vi.spyOn(clientModule.apiClient, "generateCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan,
      generated_at: "2026-06-07T12:00:00Z",
    });
    const view = render(
      <MemoryRouter>
        <AutomationCenterPage />
      </MemoryRouter>,
    );
    const btn = await screen.findByTestId("collector-advisor-generate");
    fireEvent.click(btn);
    expect(generate).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { level: 2, name: "Today's actions" })).toBeInTheDocument();
    view.unmount();
  });
});
