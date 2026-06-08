import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, type P88MarketplaceCommandCenterRead } from "../../api/client";
import { MarketplaceCommandCenterPage } from "../MarketplaceCommandCenterPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

function emptyDashboard(): P88MarketplaceCommandCenterRead {
  return {
    kpis: {
      active_opportunities: 0,
      marketplace_alerts: 0,
      price_drops: 0,
      watchlist_matches: 0,
      collection_gaps: 0,
      upcoming_releases: 0,
    },
    best_deals_today: [],
    recommended_buys_today: [],
    watchlist_opportunities_today: [],
    price_drops: [],
    collection_gaps: [],
    watchlist_matches: [],
    upcoming_releases: [],
    top_recommendations: [],
    marketplace_activity: [],
    quick_actions: [
      { label: "View Buy Opportunities", route: "/buy-opportunities", action_type: "VIEW_BUY_OPPORTUNITIES" },
    ],
    briefing_summary: {
      best_deal_title: null,
      largest_price_drop_title: null,
      top_recommendation_title: null,
      watchlist_match_title: null,
    },
    generated_at: new Date().toISOString(),
  };
}

function populatedDashboard(): P88MarketplaceCommandCenterRead {
  return {
    ...emptyDashboard(),
    kpis: {
      active_opportunities: 3,
      marketplace_alerts: 1,
      price_drops: 1,
      watchlist_matches: 1,
      collection_gaps: 2,
      upcoming_releases: 4,
    },
    best_deals_today: [
      {
        opportunity_id: 1,
        title: "Absolute Batman #20",
        marketplace: "EBAY",
        marketplace_name: "eBay",
        price: 8.99,
        fmv: 14,
        upside_percent: 56,
        savings_vs_highest: 4,
        opportunity_score: 88,
        recommendation: "STRONG_BUY",
        has_verified_listing: true,
        action_url: "https://www.ebay.com/itm/1234567890",
        action_url_type: "MARKETPLACE_LISTING",
      },
    ],
    price_drops: [
      {
        opportunity_id: 2,
        listing_id: 5,
        title: "Battle Beast #1",
        marketplace: "EBAY",
        marketplace_name: "eBay",
        old_price: 20,
        new_price: 14,
        drop_percent: 30,
      },
    ],
    watchlist_matches: [
      {
        alert_id: 9,
        saved_search_name: "TMNT",
        title: "TMNT #300",
        marketplace: "EBAY",
        marketplace_name: "eBay",
        price: 12,
        message: "New listing detected.",
        alert_type: "NEW_LISTING",
      },
    ],
    collection_gaps: [
      {
        gap_id: 1,
        title: "X-Men #1",
        reason: "Missing issue",
        gap_type: "MISSING_ISSUE",
        priority: "HIGH",
      },
    ],
    top_recommendations: [
      {
        opportunity_id: 1,
        title: "Absolute Batman #20",
        cover_image_url: "",
        score: 88,
        reason_summary: "Listed below FMV",
        best_marketplace_name: "eBay",
        best_price: 8.99,
        recommendation: "STRONG_BUY",
      },
    ],
  };
}

describe("MarketplaceCommandCenterPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders empty states", async () => {
    vi.spyOn(apiClient, "getMarketplaceCommandCenter").mockResolvedValue(emptyDashboard());
    render(
      <MemoryRouter>
        <MarketplaceCommandCenterPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Marketplace Command Center", level: 1 })).toBeInTheDocument();
    });
    expect(screen.getByText("No marketplace signals yet")).toBeInTheDocument();
    expect(screen.getByText("No verified marketplace deals in cache.")).toBeInTheDocument();
  });

  it("renders populated sections", async () => {
    vi.spyOn(apiClient, "getMarketplaceCommandCenter").mockResolvedValue(populatedDashboard());
    render(
      <MemoryRouter>
        <MarketplaceCommandCenterPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getAllByText("Absolute Batman #20").length).toBeGreaterThan(0);
    });
    expect(screen.getByRole("heading", { name: "Verified deals", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Recent price drops")).toBeInTheDocument();
    expect(screen.getByText("Battle Beast #1")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Watchlist matches", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Collection gaps", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("ComicOS top recommendations")).toBeInTheDocument();
    expect(screen.getByText("Active opportunities")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Buy Now" })).toHaveAttribute(
      "href",
      "https://www.ebay.com/itm/1234567890",
    );
  });
});
