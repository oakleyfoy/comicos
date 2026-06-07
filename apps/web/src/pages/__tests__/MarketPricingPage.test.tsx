import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { MarketPricingPage } from "../MarketPricingPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const snapshot = {
  id: 1,
  owner_user_id: 1,
  series: "Amazing Spider-Man",
  issue_number: "300",
  variant: "",
  display_title: "Amazing Spider-Man #300",
  quick_sale_price: 32,
  market_price: 38,
  premium_price: 45,
  pricing_confidence: "HIGH" as const,
  sales_velocity: "FAST" as const,
  sales_velocity_label: "Likely to sell quickly",
  listing_count: 5,
  sold_count: 2,
  price_low: 30,
  price_high: 48,
  price_average: 38,
  trend_direction: "UP" as const,
  snapshot_date: "2026-06-08",
  created_at: "2026-06-08T00:00:00Z",
};

describe("MarketPricingPage", () => {
  it("renders dashboard sections and pricing cards", async () => {
    vi.spyOn(clientModule.apiClient, "getMarketPricingDashboard").mockResolvedValue({
      highest_value_books: [snapshot],
      fastest_selling_books: [snapshot],
      largest_price_increases: [snapshot],
      largest_price_decreases: [],
      highest_confidence_pricing: [snapshot],
    });

    render(
      <MemoryRouter>
        <MarketPricingPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Market Pricing Intelligence", level: 1 })).toBeInTheDocument();
    });
    expect(screen.getByText("Highest Value Books")).toBeInTheDocument();
    expect(screen.getAllByText(/\$38\.00/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Likely to sell quickly/i).length).toBeGreaterThan(0);
  });

  it("renders empty sections gracefully", async () => {
    vi.spyOn(clientModule.apiClient, "getMarketPricingDashboard").mockResolvedValue({
      highest_value_books: [],
      fastest_selling_books: [],
      largest_price_increases: [],
      largest_price_decreases: [],
      highest_confidence_pricing: [],
    });

    render(
      <MemoryRouter>
        <MarketPricingPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/No market pricing snapshots yet/i)).toBeInTheDocument();
  });
});
