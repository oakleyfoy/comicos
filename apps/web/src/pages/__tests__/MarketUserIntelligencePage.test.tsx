import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { MarketUserIntelligencePage } from "../MarketUserIntelligencePage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const mockDashboard = {
  top_market_demand: [{ entity_type: "FRANCHISE", entity_name: "Batman", demand_score: 94, confidence_score: 0.85 }],
  top_user_preferences: [
    {
      id: 1,
      preference_type: "FRANCHISE",
      preference_key: "batman",
      preference_label: "Batman",
      status: "ACTIVE",
      preference_score: 80,
      confidence_score: 0.9,
    },
  ],
  preference_signals: [],
  market_demand_distribution: [{ bucket: "90+", count: 1 }],
  upcoming_high_fit: [],
  total_market_profiles: 22,
  total_active_preferences: 1,
};

describe("MarketUserIntelligencePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "postMarketUserIntelligenceRefresh").mockResolvedValue({
      market: { seeded_baselines: 22 },
      user_preferences: { profiles_updated: 0 },
    });
    vi.spyOn(apiClient, "getMarketUserIntelligenceDashboard").mockResolvedValue(mockDashboard);
  });

  it("renders market and user intelligence dashboard", async () => {
    render(
      <MemoryRouter>
        <MarketUserIntelligencePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Market & User Intelligence" })).toBeInTheDocument();
    });

    expect(screen.getByText("Top Market Demand")).toBeInTheDocument();
    expect(screen.getAllByText(/Batman/).length).toBeGreaterThan(0);
  });
});
