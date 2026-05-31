import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ForecastPlatformPage } from "../ForecastPlatformPage";

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

describe("ForecastPlatformPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getForecastPlatformDashboard").mockResolvedValue({
      summary: {
        market_score: 72.5,
        forecast_count: 12,
        risk_count: 4,
        recommendation_count: 7,
        forecast_accuracy: 0.84,
        top_bullish_forecasts: [],
        top_bearish_forecasts: [],
        top_risks: [{ id: 1, owner_user_id: 1, assessment_uuid: "risk-1", asset_type: "marketplace_listing", asset_id: 1, risk_type: "HIGH_VOLATILITY_RISK", risk_score: 0.62, confidence_score: 0.8, created_at: "2026-05-30T12:00:00Z" }],
        top_buy_recommendations: [{ id: 1, owner_user_id: 1, recommendation_uuid: "buy-1", recommendation_type: "BUY", asset_type: "marketplace_listing", asset_id: 1, title: "Acquire additional copies", description: "Advisory buy", confidence_score: 0.8, priority_score: 0.86, recommendation_status: "OPEN", created_at: "2026-05-30T12:00:00Z" }],
        top_sell_recommendations: [],
        top_grade_candidates: [],
        accuracy_summary: [],
        signal_quality_summary: [],
        recent_outcomes: [],
      },
      health: {
        overall_status: "HEALTHY",
        components: [
          { component_code: "market_intelligence_health", title: "Market Intelligence Health", health_status: "HEALTHY", summary: "Signals healthy.", details_json: {} },
          { component_code: "forecast_generation_health", title: "Forecast Generation Health", health_status: "HEALTHY", summary: "Forecasts healthy.", details_json: {} },
          { component_code: "risk_assessment_health", title: "Risk Assessment Health", health_status: "WARNING", summary: "Risk pipeline warming.", details_json: {} },
          { component_code: "dealer_copilot_health", title: "Dealer Copilot Health", health_status: "HEALTHY", summary: "Recommendations healthy.", details_json: {} },
          { component_code: "validation_learning_health", title: "Validation and Learning Health", health_status: "HEALTHY", summary: "Validation healthy.", details_json: {} },
          { component_code: "agent_execution_health", title: "Agent Execution Health", health_status: "HEALTHY", summary: "Executions healthy.", details_json: {} },
        ],
      },
      validation: {
        overall_status: "PASS",
        platform_certified: true,
        checks: [
          { check_code: "market_intelligence", title: "Market Intelligence", status: "PASS", summary: "Looks good.", details_json: {} },
          { check_code: "forecasts", title: "Forecasts", status: "PASS", summary: "Looks good.", details_json: {} },
        ],
      },
      certification: {
        platform_certified: true,
        validation_status: "PASS",
        health_status: "HEALTHY",
        summary: "Certified",
        certification_notes: ["Forecast platform passed closeout validation and is certified for the P47 decision-intelligence layer."],
      },
    });
  });

  it("renders forecast platform dashboard sections", async () => {
    render(
      <MemoryRouter>
        <ForecastPlatformPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Forecast Platform" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Market Score")).toBeInTheDocument();
      expect(screen.getByText("Top Opportunities")).toBeInTheDocument();
      expect(screen.getByText("Top Risks")).toBeInTheDocument();
      expect(screen.getByText("Certification Status")).toBeInTheDocument();
      expect(screen.getAllByText("Buy: Acquire additional copies").length).toBeGreaterThan(0);
    });
  });
});
