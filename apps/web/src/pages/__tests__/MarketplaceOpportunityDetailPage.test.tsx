import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, type P82MarketplaceAcquisitionOpportunityRead } from "../../api/client";
import { MarketplaceOpportunityDetailPage } from "../MarketplaceOpportunityDetailPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

function baseOpp(
  partial: Partial<P82MarketplaceAcquisitionOpportunityRead> = {},
): P82MarketplaceAcquisitionOpportunityRead {
  return {
    id: 1,
    marketplace: "EBAY",
    external_listing_id: "SIM-EBAY-P82-99",
    listing_url: "https://www.ebay.com/itm/SIM-EBAY-P82-99",
    title: "Test Comic #1",
    publisher: "DC",
    series: "Test Comic",
    issue: "1",
    variant: "",
    asking_price: 10,
    estimated_fmv: 20,
    discount_to_fmv: 50,
    liquidity: 0,
    velocity: 0,
    grading_upside: 0,
    ownership_status: "GAP",
    profile_match_score: 0,
    opportunity_score: 81,
    recommendation: "GOOD_BUY",
    reasons: ["Listed below estimated FMV."],
    status: "ACTIVE",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...partial,
  };
}

describe("MarketplaceOpportunityDetailPage listing safety", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("shows no-live-listing message for simulated IDs and hides outbound link", async () => {
    vi.spyOn(apiClient, "getMarketplaceAcquisitionOpportunity").mockResolvedValue(baseOpp());
    render(
      <MemoryRouter initialEntries={["/marketplace-opportunity/1"]}>
        <Routes>
          <Route path="/marketplace-opportunity/:id" element={<MarketplaceOpportunityDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(
        screen.getByText("No live marketplace listing is available for this opportunity yet."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: "View Marketplace Listing" })).not.toBeInTheDocument();
    expect(screen.queryByText(/GOOD_BUY/i)).not.toBeInTheDocument();
    expect(screen.getByText("Strong Buy")).toBeInTheDocument();
  });

  it("shows View Marketplace Listing for numeric eBay item URL", async () => {
    vi.spyOn(apiClient, "getMarketplaceAcquisitionOpportunity").mockResolvedValue(
      baseOpp({
        external_listing_id: "123456789012",
        listing_url: "https://www.ebay.com/itm/123456789012",
      }),
    );
    render(
      <MemoryRouter initialEntries={["/marketplace-opportunity/1"]}>
        <Routes>
          <Route path="/marketplace-opportunity/:id" element={<MarketplaceOpportunityDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("link", { name: "View Marketplace Listing" })).toHaveAttribute(
        "href",
        "https://www.ebay.com/itm/123456789012",
      );
    });
    expect(
      screen.queryByText("No live marketplace listing is available for this opportunity yet."),
    ).not.toBeInTheDocument();
  });
});
