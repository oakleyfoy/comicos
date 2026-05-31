import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DealerCopilotPage } from "../DealerCopilotPage";
import { apiClient } from "../../api/client";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
      {actions}
    </header>
  ),
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("DealerCopilotPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getDealerCopilotDashboard").mockResolvedValue({
      summary: {
        total_recommendations: 6,
        open_recommendations: 4,
        by_type: { BUY: 2, SELL: 1, HOLD: 1, GRADE: 1, WATCH: 1 },
        by_status: { OPEN: 4, REVIEWED: 1, ACCEPTED: 1 },
      },
      top_buys: [
        {
          id: 1,
          owner_user_id: 1,
          agent_execution_id: 11,
          recommendation_uuid: "buy-1",
          recommendation_type: "BUY",
          asset_type: "marketplace_listing",
          asset_id: 101,
          title: "Acquire additional copies",
          description: "Strong demand with favorable forecasts.",
          confidence_score: 0.82,
          priority_score: 0.88,
          recommendation_status: "OPEN",
          created_at: "2026-05-30T12:00:00Z",
          latest_review: null,
        },
      ],
      top_sells: [],
      top_holds: [],
      top_grades: [],
      top_watchlist: [],
      opportunities: [
        {
          id: 1,
          owner_user_id: 1,
          asset_type: "marketplace_listing",
          asset_id: 101,
          opportunity_score: 0.88,
          risk_score: 0.22,
          forecast_score: 0.84,
          demand_score: 0.79,
          grading_score: 0.61,
          calculated_at: "2026-05-30T12:00:00Z",
        },
      ],
      executions: [
        {
          id: 1,
          owner_user_id: 1,
          agent_code: "buy_list_agent",
          execution_uuid: "exec-1",
          status: "COMPLETED",
          started_at: "2026-05-30T12:00:00Z",
          completed_at: "2026-05-30T12:00:03Z",
          duration_ms: 3000,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
    });
    vi.spyOn(apiClient, "runDealerCopilot").mockResolvedValue({
      recommendations: [],
      opportunities: [],
      executions: [],
    });
  });

  it("renders dealer copilot panels and can run the copilot", async () => {
    render(
      <MemoryRouter>
        <DealerCopilotPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Dealer Copilot" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Top Buy Opportunities")).toBeInTheDocument();
      expect(screen.getAllByText("Acquire additional copies").length).toBeGreaterThan(0);
      expect(screen.getByText("Opportunity Scores")).toBeInTheDocument();
      expect(screen.getAllByText("Agent Activity").length).toBeGreaterThan(0);
    });

    fireEvent.click(screen.getByRole("button", { name: "Run Copilot" }));
    await waitFor(() => {
      expect(apiClient.runDealerCopilot).toHaveBeenCalledTimes(1);
      expect(apiClient.getDealerCopilotDashboard).toHaveBeenCalledTimes(2);
    });
  });
});
