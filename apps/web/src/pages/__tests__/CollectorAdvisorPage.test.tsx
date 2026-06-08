import { MemoryRouter, Route, Routes } from "react-router-dom";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as apiClient from "../../api/client";
import { AutomationCenterPage } from "../AutomationCenterPage";
import {
  COLLECTOR_ADVISOR_GENERATE_CTA,
  COLLECTOR_ADVISOR_GENERATE_PLAN_CTA,
  COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_SIGNALS,
  COLLECTOR_ADVISOR_MESSAGE_GATHER_FAILED,
  COLLECTOR_ADVISOR_NO_PLAN_MESSAGE,
  COLLECTOR_ADVISOR_OPPORTUNITY_VALUE_TITLE,
  COLLECTOR_ADVISOR_SUBTITLE,
  COLLECTOR_ADVISOR_TODAYS_BEST_ACTIONS_TITLE,
} from "../collectorAdvisorPresentation";
import { dedupeEvidenceString, stripAdvisorTitlePrefixes } from "../advisorRecommendationPresentation";

const useAuthMock = vi.fn(() => ({ isOpsAdmin: false, isAuthenticated: true, isLoading: false }));

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => useAuthMock(),
}));

const plan: apiClient.P90CollectorAdvisorSnapshotRead = {
  id: 1,
  snapshot_date: "2026-06-07",
  buy_actions: [
    {
      category: "BUY",
      comic: "Absolute Batman #20",
      reason: "55% below FMV · verified listing · 55% below FMV · 26% below FMV",
      primary_reason: "55% below FMV",
      supporting_signals: ["verified listing", "26% below FMV"],
      hidden_signal_count: 0,
      confidence: "HIGH",
      priority_score: 89,
      potential_upside: 6,
      action_route: "/marketplace-opportunity/1",
      source_system: "P88",
      display_label: "Absolute Batman #20",
    },
  ],
  sell_actions: [],
  grade_actions: [],
  watch_actions: [],
  todays_actions: [
    {
      rank: 1,
      category: "BUY",
      title: "Absolute Batman #20",
      detail: "55% below FMV",
      priority_score: 89,
      action_route: "/marketplace-opportunity/1",
      potential_upside: 6,
    },
  ],
  recent_activity: [],
  market_alerts: [],
  total_actions: 1,
  portfolio_impact: {
    potential_profit: 0,
    potential_savings: 6,
    potential_value_gain: 0,
    portfolio_impact_total: 6,
    portfolio_score: 42,
  },
  created_at: "2026-06-07T12:00:00Z",
};

const emptyPlan: apiClient.P90CollectorAdvisorSnapshotRead = {
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

function renderPage(path = "/automation-center") {
  const entry = path.includes("?")
    ? { pathname: path.split("?")[0], search: `?${path.split("?")[1]}` }
    : path;
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/automation-center" element={<AutomationCenterPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("advisorRecommendationPresentation", () => {
  it("removes duplicate evidence segments", () => {
    expect(
      dedupeEvidenceString("55% below FMV · verified listing · 55% below FMV · verified listing · 26% below FMV"),
    ).toBe("55% below FMV · verified listing · 26% below FMV");
  });

  it("strips redundant buy prefixes from titles", () => {
    expect(stripAdvisorTitlePrefixes("Buy Good Buy: Absolute Batman #20", "BUY")).toBe("Absolute Batman #20");
  });
});

describe("CollectorAdvisorPage", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    useAuthMock.mockReturnValue({ isOpsAdmin: false, isAuthenticated: true, isLoading: false });
  });

  it("renders dashboard and opportunity value", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan,
      generated_at: "2026-06-07T12:00:00Z",
    });
    renderPage();
    expect(await screen.findByText("Collector Advisor")).toBeInTheDocument();
    expect(screen.getAllByText("Absolute Batman #20").length).toBeGreaterThan(0);
    expect(screen.getByText(COLLECTOR_ADVISOR_OPPORTUNITY_VALUE_TITLE)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: COLLECTOR_ADVISOR_GENERATE_PLAN_CTA })).toBeInTheDocument();
  });

  it("renders NO_SNAPSHOT empty state", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "NO_SNAPSHOT",
      plan: null,
      message: COLLECTOR_ADVISOR_NO_PLAN_MESSAGE,
      generated_at: "2026-06-07T12:00:00Z",
    });
    renderPage();
    expect(await screen.findByText(COLLECTOR_ADVISOR_SUBTITLE)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: COLLECTOR_ADVISOR_GENERATE_CTA })).toBeInTheDocument();
  });

  it("renders EMPTY_NO_SIGNALS without empty section boxes", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "EMPTY_NO_SIGNALS",
      plan: emptyPlan,
      message: COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_SIGNALS,
      generated_at: "2026-06-07T12:00:00Z",
    });
    renderPage();
    expect(await screen.findByTestId("collector-advisor-status-banner")).toHaveTextContent(
      COLLECTOR_ADVISOR_MESSAGE_EMPTY_NO_SIGNALS,
    );
    expect(screen.queryByRole("heading", { name: "Sell", level: 2 })).not.toBeInTheDocument();
  });

  it("collapses empty secondary sections when buy data exists", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan,
      generated_at: "2026-06-07T12:00:00Z",
    });
    renderPage();
    await screen.findByRole("heading", { name: "Buy", level: 2 });
    expect(screen.queryByRole("heading", { name: "Sell", level: 2 })).not.toBeInTheDocument();
    expect(screen.getByText(/No sell, grade, watch, or market alerts require attention today/i)).toBeInTheDocument();
  });

  it("hides ops diagnostics without debug flag", async () => {
    useAuthMock.mockReturnValue({ isOpsAdmin: true, isAuthenticated: true, isLoading: false });
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan,
      generated_at: "2026-06-07T12:00:00Z",
      signal_diagnostics: {
        inventory_count: 70,
        marketplace_opportunity_count: 5,
        marketplace_alert_count: 0,
        sell_candidate_count: 70,
        listing_draft_count: 0,
        managed_listing_count: 0,
        future_pull_count: 0,
        discovery_alert_count: 0,
        collection_gap_count: 0,
        automation_alert_count: 5,
        fmv_snapshot_count: 0,
        grade_before_sell_count: 0,
        grading_candidate_count: 0,
        gather_failed_subsystems: [],
        gather_errors: [],
      },
    });
    renderPage();
    await screen.findByRole("heading", { name: "Buy", level: 2 });
    expect(screen.queryByTestId("advisor-ops-diagnostics")).not.toBeInTheDocument();
  });

  it("shows ops diagnostics for admin with debug=1", async () => {
    useAuthMock.mockReturnValue({ isOpsAdmin: true, isAuthenticated: true, isLoading: false });
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan,
      generated_at: "2026-06-07T12:00:00Z",
      signal_diagnostics: {
        inventory_count: 1,
        marketplace_opportunity_count: 1,
        marketplace_alert_count: 0,
        sell_candidate_count: 0,
        listing_draft_count: 0,
        managed_listing_count: 0,
        future_pull_count: 0,
        discovery_alert_count: 0,
        collection_gap_count: 0,
        automation_alert_count: 0,
        fmv_snapshot_count: 0,
        grade_before_sell_count: 0,
        grading_candidate_count: 0,
        gather_failed_subsystems: [],
        gather_errors: [],
      },
    });
    renderPage("/automation-center?debug=1");
    expect(await screen.findByTestId("advisor-ops-diagnostics")).toBeInTheDocument();
  });

  it("shows Buy Now on buy card when verified listing action is present", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan: {
        ...plan,
        buy_actions: [
          {
            ...plan.buy_actions[0],
            action_url: "https://www.ebay.com/itm/1234567890",
            action_url_type: "MARKETPLACE_LISTING",
            has_verified_listing: true,
            marketplace_name: "eBay",
          },
        ],
      },
      generated_at: "2026-06-07T12:00:00Z",
    });
    renderPage();
    await screen.findByRole("heading", { name: "Buy", level: 2 });
    expect(screen.getByRole("link", { name: "Buy Now" })).toHaveAttribute(
      "href",
      "https://www.ebay.com/itm/1234567890",
    );
  });

  it("shows Review on buy card without verified listing", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan: {
        ...plan,
        buy_actions: [
          {
            ...plan.buy_actions[0],
            action_url: "/marketplace-opportunity/1",
            action_url_type: "OPPORTUNITY_DETAIL",
            has_verified_listing: false,
          },
        ],
      },
      generated_at: "2026-06-07T12:00:00Z",
    });
    renderPage();
    await screen.findByRole("heading", { name: "Buy", level: 2 });
    expect(screen.getByRole("link", { name: "Review Opportunity" })).toHaveAttribute("href", "/marketplace-opportunity/1");
    expect(screen.queryByRole("link", { name: "Buy Now" })).not.toBeInTheDocument();
  });

  it("renders Today's Best Actions section", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan,
      generated_at: "2026-06-07T12:00:00Z",
    });
    renderPage();
    expect(await screen.findByRole("heading", { name: COLLECTOR_ADVISOR_TODAYS_BEST_ACTIONS_TITLE, level: 2 })).toBeInTheDocument();
  });

  it("calls generate when empty CTA is clicked", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "NO_SNAPSHOT",
      plan: null,
      generated_at: "2026-06-07T12:00:00Z",
    });
    const generate = vi.spyOn(apiClient.apiClient, "generateCollectorAdvisor").mockResolvedValue({
      status: "OK",
      plan,
      generated_at: "2026-06-07T12:00:00Z",
    });
    renderPage();
    fireEvent.click(await screen.findByTestId("collector-advisor-generate"));
    expect(generate).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: COLLECTOR_ADVISOR_TODAYS_BEST_ACTIONS_TITLE, level: 2 })).toBeInTheDocument();
  });

  it("renders EMPTY_GATHER_FAILED try again", async () => {
    vi.spyOn(apiClient.apiClient, "getCollectorAdvisor").mockResolvedValue({
      status: "EMPTY_GATHER_FAILED",
      plan: emptyPlan,
      message: COLLECTOR_ADVISOR_MESSAGE_GATHER_FAILED,
      generated_at: "2026-06-07T12:00:00Z",
    });
    renderPage();
    expect(await screen.findByTestId("collector-advisor-status-banner")).toHaveTextContent(
      COLLECTOR_ADVISOR_MESSAGE_GATHER_FAILED,
    );
    expect(screen.getByRole("button", { name: "Try Again" })).toBeInTheDocument();
  });
});
