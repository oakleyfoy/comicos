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
});
