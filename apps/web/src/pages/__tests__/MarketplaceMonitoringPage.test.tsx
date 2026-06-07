import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { MarketplaceMonitoringPage } from "../MarketplaceMonitoringPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("MarketplaceMonitoringPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "listMarketplaceSavedSearches").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "listMarketplaceMonitoringAlerts").mockResolvedValue({ items: [] });
    vi.spyOn(apiClient, "listMarketplaceMonitoringRuns").mockResolvedValue({ items: [] });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders saved search form and empty states", async () => {
    render(
      <MemoryRouter>
        <MarketplaceMonitoringPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Marketplace Monitoring", level: 1 })).toBeInTheDocument();
    });
    expect(screen.getByText("No saved searches yet. Create one to start monitoring eBay.")).toBeInTheDocument();
    expect(screen.getByText("No new alerts.")).toBeInTheDocument();
  });

  it("Run Now calls API", async () => {
    vi.spyOn(apiClient, "listMarketplaceSavedSearches").mockResolvedValue({
      items: [
        {
          id: 1,
          name: "Batman",
          marketplace: "EBAY",
          query: "",
          series: "Absolute Batman",
          issue_number: "20",
          publisher: "",
          variant: "",
          max_price: null,
          min_discount_to_fmv: 15,
          condition_filter: "",
          is_active: true,
          last_run_at: null,
          last_success_at: null,
          last_error: "",
          created_at: "",
          updated_at: "",
        },
      ],
    });
    const run = vi.spyOn(apiClient, "runMarketplaceSavedSearch").mockResolvedValue({
      saved_search: {} as never,
      run: {
        id: 1,
        saved_search_id: 1,
        searches_run: 1,
        listings_found: 0,
        new_listings: 0,
        price_drops: 0,
        below_fmv_alerts: 0,
        watchlist_matches: 0,
        errors: [],
        created_at: new Date().toISOString(),
      },
    });
    render(
      <MemoryRouter>
        <MarketplaceMonitoringPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Run Now")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Run Now"));
    await waitFor(() => {
      expect(run).toHaveBeenCalledWith(1);
    });
  });

  it("dismiss alert calls API", async () => {
    vi.spyOn(apiClient, "listMarketplaceMonitoringAlerts").mockResolvedValue({
      items: [
        {
          id: 9,
          saved_search_id: 1,
          opportunity_id: null,
          listing_id: 1,
          alert_type: "NEW_LISTING",
          title: "Test Book",
          message: "New listing",
          severity: "MEDIUM",
          status: "NEW",
          marketplace: "EBAY",
          listing_url: "https://www.ebay.com/itm/1234567890",
          external_item_id: "1234567890",
          price: 5,
          shipping_cost: 0,
          estimated_fmv: null,
          created_at: new Date().toISOString(),
          acknowledged_at: null,
        },
      ],
    });
    const dismiss = vi.spyOn(apiClient, "updateMarketplaceAlert").mockResolvedValue({} as never);
    render(
      <MemoryRouter>
        <MarketplaceMonitoringPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("New Listing")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Dismiss"));
    await waitFor(() => {
      expect(dismiss).toHaveBeenCalledWith(9, { status: "DISMISSED" });
    });
  });
});
