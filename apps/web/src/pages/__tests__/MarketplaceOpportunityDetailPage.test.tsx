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
    vi.spyOn(apiClient, "listBuyOpportunitySources").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "listBuyOpportunityMarketplaceListings").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "getBuyOpportunityMarketplaceComparison").mockResolvedValue({
      comparison: { best_marketplace: null, best_marketplace_name: null, best_price: null, best_total_cost: null, savings_vs_highest: null, rankings: [] },
      best_buy: { marketplace: null, marketplace_name: null, price: null, shipping: null, total_cost: null, reason: "", listing_confidence: null },
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("shows recommendation layout for simulated IDs without Buy Now", async () => {
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
        screen.getByText("ComicOS has not verified a live listing for this recommendation yet."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: "Buy Now" })).not.toBeInTheDocument();
    expect(screen.getAllByText("Recommended Buy").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Search Marketplaces" })).toBeInTheDocument();
  });

  it("shows Buy Now for verified best_verified_listing", async () => {
    vi.spyOn(apiClient, "getMarketplaceAcquisitionOpportunity").mockResolvedValue(
      baseOpp({
        external_listing_id: "123456789012",
        listing_url: "https://www.ebay.com/itm/123456789012",
        has_verified_listings: true,
        is_verified_deal: true,
        recommendation_type: "VERIFIED_DEAL",
        verified_listing_count: 1,
        best_verified_listing: {
          marketplace: "EBAY",
          marketplace_name: "eBay",
          listing_url: "https://www.ebay.com/itm/123456789012",
          price: 4.49,
          shipping: 0,
          total_cost: 4.49,
          seller: "",
          condition: "",
          last_verified_at: new Date().toISOString(),
          confidence: "HIGH",
        },
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
      expect(screen.getByRole("link", { name: "Buy Now" })).toHaveAttribute(
        "href",
        "https://www.ebay.com/itm/123456789012",
      );
    });
    expect(screen.getByText("Verified Deal")).toBeInTheDocument();
    expect(
      screen.queryByText("ComicOS has not verified a live listing for this recommendation yet."),
    ).not.toBeInTheDocument();
  });

  it("without verified payload does not show Buy Now in header CTA", async () => {
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
      expect(screen.getAllByText("Recommended Buy").length).toBeGreaterThan(0);
    });
    expect(screen.queryByRole("link", { name: "Buy Now" })).not.toBeInTheDocument();
  });

  it("shows marketplace listings section for verified active listings", async () => {
    vi.spyOn(apiClient, "getMarketplaceAcquisitionOpportunity").mockResolvedValue(
      baseOpp({
        external_listing_id: "123456789012",
        listing_url: "https://www.ebay.com/itm/123456789012",
        has_verified_listings: true,
        active_listing_count: 1,
        best_active_price: 3.2,
      }),
    );
    vi.spyOn(apiClient, "listBuyOpportunityMarketplaceListings").mockResolvedValue({
      items: [
        {
          id: 10,
          marketplace: "EBAY",
          item_id: "123456789012",
          title: "Test Comic #1",
          listing_url: "https://www.ebay.com/itm/123456789012",
          image_url: "",
          price: 3.2,
          shipping_cost: 4.95,
          condition: "VF/NM",
          seller_name: "comicshop123",
          listing_type: "FIXED_PRICE",
          end_time: null,
          is_active: true,
          health_status: "ACTIVE",
          health_badges: ["Verified Today"],
          last_verified_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total_items: 1,
    });
    render(
      <MemoryRouter initialEntries={["/marketplace-opportunity/1"]}>
        <Routes>
          <Route path="/marketplace-opportunity/:id" element={<MarketplaceOpportunityDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Marketplace listings")).toBeInTheDocument();
    });
    expect(screen.getByText("Seller: comicshop123")).toBeInTheDocument();
    expect(screen.getAllByText("Verified Today").length).toBeGreaterThan(0);
  });

  it("renders marketplace comparison table with best badge", async () => {
    vi.spyOn(apiClient, "getMarketplaceAcquisitionOpportunity").mockResolvedValue(baseOpp());
    vi.spyOn(apiClient, "getBuyOpportunityMarketplaceComparison").mockResolvedValue({
      comparison: {
        best_marketplace: "EBAY",
        best_marketplace_name: "eBay",
        best_price: 8.99,
        best_total_cost: 8.99,
        savings_vs_highest: 4,
        rankings: [
          {
            marketplace: "EBAY",
            marketplace_name: "eBay",
            price: 8.99,
            shipping: 0,
            overall_cost: 8.99,
            availability_status: "ACTIVE",
            listing_confidence: "HIGH",
            listing_count: 3,
            is_best: true,
          },
          {
            marketplace: "MIDTOWN",
            marketplace_name: "Midtown Comics",
            price: 12.99,
            shipping: 0,
            overall_cost: 12.99,
            availability_status: "ACTIVE",
            listing_confidence: "LOW",
            listing_count: 1,
            is_best: false,
          },
        ],
      },
      best_buy: {
        marketplace: "EBAY",
        marketplace_name: "eBay",
        price: 8.99,
        shipping: 0,
        total_cost: 8.99,
        reason: "Lowest total cost available.",
        listing_confidence: "HIGH",
      },
    });
    render(
      <MemoryRouter initialEntries={["/marketplace-opportunity/1"]}>
        <Routes>
          <Route path="/marketplace-opportunity/:id" element={<MarketplaceOpportunityDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Marketplace comparison")).toBeInTheDocument();
    });
    expect(screen.getByText("Lowest Total Cost")).toBeInTheDocument();
  });
});
