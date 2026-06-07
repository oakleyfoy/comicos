import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { MarketplaceCoverageDashboardPage } from "../MarketplaceCoverageDashboardPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("MarketplaceCoverageDashboardPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getAdminMarketplaceCoverage").mockResolvedValue({
      listings_by_marketplace: [
        {
          marketplace: "EBAY",
          marketplace_name: "eBay",
          listing_count: 7,
          supports_search: true,
          supports_listing_lookup: true,
          supports_price_tracking: true,
          supports_refresh: true,
        },
      ],
      search_success_rate_percent: 95,
      supported_marketplaces: ["eBay"],
      unsupported_marketplaces: ["MyComicShop"],
      total_listings: 7,
      registry_marketplace_count: 8,
    });
    vi.spyOn(apiClient, "getAdminMarketplaceDiagnostics").mockResolvedValue({
      adapters: [
        {
          marketplace: "EBAY",
          marketplace_name: "eBay",
          adapter_status: "READY",
          marketplace_support_status: "SUPPORTED",
          supports_search: true,
          supports_listing_lookup: true,
          supports_price_tracking: true,
          supports_refresh: true,
          listing_count: 7,
          last_successful_search: null,
          last_successful_refresh: null,
        },
      ],
      recent_errors: [],
      last_search_run_at: null,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders coverage metrics and comparison table headers", async () => {
    render(
      <MemoryRouter>
        <MarketplaceCoverageDashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Marketplace Coverage")).toBeInTheDocument();
    });
    expect(screen.getByText("Listings by marketplace")).toBeInTheDocument();
    expect(screen.getAllByText("eBay").length).toBeGreaterThan(0);
    expect(screen.getByText("Marketplace diagnostics")).toBeInTheDocument();
  });
});
