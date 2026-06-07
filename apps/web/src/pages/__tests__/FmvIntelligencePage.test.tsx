import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { FmvIntelligencePage } from "../FmvIntelligencePage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const payload: clientModule.P90FmvIntelligenceDashboardRead = {
  status: "OK",
  generated_at: new Date().toISOString(),
  portfolio: {
    quick_liquidation_total: 100,
    market_portfolio_value: 120,
    premium_portfolio_value: 140,
    portfolio_trend: "UP",
    confidence_high: 2,
    confidence_medium: 1,
    confidence_low: 0,
  },
  highest_value: [
    {
      id: 1,
      series: "ASM",
      issue_number: "300",
      variant: "",
      quick_sale_value: 32,
      market_value: 38,
      premium_value: 45,
      valuation_confidence: "HIGH",
      trend_direction: "UP",
      trend_score: 72,
      sales_velocity: "FAST",
      listing_count: 5,
      marketplace_count: 2,
      valuation_source: "MARKETPLACE",
      snapshot_date: "2026-06-07",
      created_at: new Date().toISOString(),
    },
  ],
  largest_movers: [],
  strongest_uptrends: [],
  strongest_downtrends: [],
  highest_confidence: [],
  lowest_confidence: [],
};

describe("FmvIntelligencePage", () => {
  it("renders dashboard and confidence", async () => {
    vi.spyOn(clientModule.apiClient, "getFmvIntelligence").mockResolvedValue(payload);
    render(
      <MemoryRouter>
        <FmvIntelligencePage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "FMV Intelligence", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Portfolio FMV V2", level: 2 })).toBeInTheDocument();
    expect(screen.getByText(/HIGH confidence/)).toBeInTheDocument();
    expect(screen.getByText(/Trend UP/)).toBeInTheDocument();
  });

  it("renders empty state", async () => {
    vi.spyOn(clientModule.apiClient, "getFmvIntelligence").mockResolvedValue({
      ...payload,
      highest_value: [],
      portfolio: { ...payload.portfolio, market_portfolio_value: 0 },
    });
    render(
      <MemoryRouter>
        <FmvIntelligencePage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("No FMV V2 snapshots")).toBeInTheDocument();
  });
});
