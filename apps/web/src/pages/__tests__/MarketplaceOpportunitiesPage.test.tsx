import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { NAV_GROUPS } from "../../config/appNavigation";
import { MarketplaceOpportunitiesPage } from "../MarketplaceOpportunitiesPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("MarketplaceOpportunitiesPage (Buy Opportunities)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "listMarketplaceAcquisitionOpportunities").mockResolvedValue({
      items: [],
      status: "OK",
      message: "",
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("shows Buy Opportunities title and subtitle", async () => {
    render(
      <MemoryRouter initialEntries={["/buy-opportunities"]}>
        <Routes>
          <Route path="/buy-opportunities" element={<MarketplaceOpportunitiesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Buy Opportunities", level: 1 })).toBeInTheDocument();
    });
    expect(
      screen.getByText(/Comics identified by ComicOS as strong purchase opportunities/i),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Marketplace opportunities/i)).not.toBeInTheDocument();
  });

  it("renders on legacy /marketplace-opportunities route", async () => {
    render(
      <MemoryRouter initialEntries={["/marketplace-opportunities"]}>
        <Routes>
          <Route path="/marketplace-opportunities" element={<MarketplaceOpportunitiesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getAllByRole("heading", { name: "Buy Opportunities", level: 1 }).length).toBeGreaterThan(0);
    });
  });

  it("shows Buy Opportunities in BUY sidebar nav config", () => {
    const buyGroup = NAV_GROUPS.find((g) => g.id === "buy");
    const link = buyGroup?.links.find((l) => l.label === "Buy Opportunities");
    expect(link?.to).toBe("/buy-opportunities");
    expect(buyGroup?.links.some((l) => l.label === "Marketplace Opportunities")).toBe(false);
  });

  it("renders structured cards without raw GOOD_BUY", async () => {
    vi.spyOn(apiClient, "listMarketplaceAcquisitionOpportunities").mockResolvedValue({
      items: [
        {
          id: 1,
          marketplace: "ebay",
          external_listing_id: "x1",
          listing_url: "",
          title: "Energon Universe #2026SPECIAL1",
          publisher: "",
          series: "Energon Universe",
          issue: "2026SPECIAL1",
          variant: "",
          asking_price: 3.2,
          estimated_fmv: 10,
          discount_to_fmv: 0,
          liquidity: 0,
          velocity: 0,
          grading_upside: 0,
          ownership_status: "",
          profile_match_score: 0,
          opportunity_score: 81,
          recommendation: "GOOD_BUY",
          reasons: [],
          status: "OPEN",
          created_at: "",
          updated_at: "",
        },
      ],
      status: "OK",
      message: "",
    });
    render(
      <MemoryRouter initialEntries={["/buy-opportunities"]}>
        <Routes>
          <Route path="/buy-opportunities" element={<MarketplaceOpportunitiesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Strong Buy")).toBeInTheDocument();
    });
    expect(screen.queryByText(/GOOD_BUY/i)).not.toBeInTheDocument();
    expect(screen.getByText(/\+213%/)).toBeInTheDocument();
    expect(screen.getByText("Top Opportunity")).toBeInTheDocument();
  });

  it("shows empty state copy when list is empty", async () => {
    render(
      <MemoryRouter initialEntries={["/buy-opportunities"]}>
        <Routes>
          <Route path="/buy-opportunities" element={<MarketplaceOpportunitiesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("No buy opportunities found right now.")).toBeInTheDocument();
    });
  });

  it("shows View Listings when verified marketplace listings exist", async () => {
    vi.spyOn(apiClient, "listMarketplaceAcquisitionOpportunities").mockResolvedValue({
      items: [
        {
          id: 1,
          marketplace: "EBAY",
          external_listing_id: "888",
          listing_url: "https://www.ebay.com/itm/888",
          title: "Absolute Batman #20",
          publisher: "DC",
          series: "Absolute Batman",
          issue: "20",
          variant: "",
          asking_price: 3.2,
          estimated_fmv: 10,
          discount_to_fmv: 0,
          liquidity: 0,
          velocity: 0,
          grading_upside: 0,
          ownership_status: "",
          profile_match_score: 0,
          opportunity_score: 90,
          recommendation: "STRONG_BUY",
          reasons: [],
          status: "ACTIVE",
          created_at: "",
          updated_at: "",
          has_verified_listings: true,
          active_listing_count: 3,
          best_active_price: 3.2,
          listing_marketplace: "EBAY",
        },
      ],
      status: "OK",
      message: "",
    });
    render(
      <MemoryRouter initialEntries={["/buy-opportunities"]}>
        <Routes>
          <Route path="/buy-opportunities" element={<MarketplaceOpportunitiesPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("View Listings")).toBeInTheDocument();
    });
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Best marketplace")).toBeInTheDocument();
  });
});
