import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import * as p67Module from "../../api/p67PortfolioAnalytics";
import { PortfolioAnalyticsPage } from "../PortfolioAnalyticsPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("Portfolio market pricing integration", () => {
  it("renders market pricing totals on portfolio analytics", async () => {
    vi.spyOn(p67Module.p67Api, "portfolioLatest").mockResolvedValue({ snapshot: null, status: "EMPTY" });
    vi.spyOn(p67Module.p67Api, "collectionLatest").mockResolvedValue({ snapshot: null, status: "EMPTY" });
    vi.spyOn(p67Module.p67Api, "recommendationLatest").mockResolvedValue({ snapshot: null, status: "EMPTY" });
    vi.spyOn(p67Module.p67Api, "gradingLatest").mockResolvedValue({ snapshot: null, status: "EMPTY" });
    vi.spyOn(p67Module.p67Api, "investorLatest").mockResolvedValue({
      status: "EMPTY",
      collection_value: 0,
      cost_basis: 0,
      unrealized_gain: 0,
      portfolio_health_score: 0,
    } as never);
    vi.spyOn(p67Module.p68Api, "latestSnapshots").mockResolvedValue({ items: [] });
    vi.spyOn(clientModule.apiClient, "getMarketPricingPortfolioTotals").mockResolvedValue({
      quick_liquidation_total: 1200,
      market_value_total: 1500,
      premium_value_total: 1800,
    });

    render(<PortfolioAnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText("Quick liquidation total")).toBeInTheDocument();
    });
    expect(screen.getByText("$1,500.00")).toBeInTheDocument();
  });
});
