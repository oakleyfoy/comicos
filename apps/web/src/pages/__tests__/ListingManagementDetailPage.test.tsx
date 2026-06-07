import { MemoryRouter, Route, Routes } from "react-router-dom";
import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { ListingManagementDetailPage } from "../ListingManagementDetailPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const listing: clientModule.P89ManagedListingRead = {
  id: 2,
  owner_user_id: 1,
  inventory_copy_id: 10,
  listing_draft_id: 5,
  marketplace: "EBAY",
  listing_url: "https://example.com/item",
  external_listing_id: "abc",
  title: "X-Men #1",
  comic_title: "X-Men #1",
  asking_price: 40,
  shipping_price: 6,
  minimum_price: 35,
  status: "ACTIVE",
  listed_at: "2026-06-02T12:00:00Z",
  sold_at: null,
  expired_at: null,
  archived_at: null,
  sale_price: null,
  shipping_charged: null,
  marketplace_fees: null,
  shipping_cost: null,
  net_profit: null,
  notes: "Test notes",
  profit: null,
  status_history: [{ status: "DRAFT", at: "2026-06-01T12:00:00Z" }],
  inventory_auto_updated: false,
  created_at: "2026-06-01T12:00:00Z",
  updated_at: "2026-06-02T12:00:00Z",
};

describe("ListingManagementDetailPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders detail sections and sold form", async () => {
    vi.spyOn(clientModule.apiClient, "getManagedListing").mockResolvedValue(listing);
    render(
      <MemoryRouter initialEntries={["/listing-management/2?markSold=1"]}>
        <Routes>
          <Route path="/listing-management/:id" element={<ListingManagementDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("X-Men #1")).toBeInTheDocument();
    expect(screen.getByText("Listing info")).toBeInTheDocument();
    expect(screen.getByText("Record sale")).toBeInTheDocument();
  });

  it("submits mark sold", async () => {
    const soldSpy = vi.spyOn(clientModule.apiClient, "markManagedListingSold").mockResolvedValue({
      ...listing,
      status: "SOLD",
      sale_price: 45,
      profit: {
        gross_sale: 45,
        total_costs: 10,
        net_profit: 35,
        profit_margin: 77.78,
        cost_basis: 5,
        cost_basis_known: true,
      },
    });
    vi.spyOn(clientModule.apiClient, "getManagedListing").mockResolvedValue(listing);
    render(
      <MemoryRouter initialEntries={["/listing-management/2?markSold=1"]}>
        <Routes>
          <Route path="/listing-management/:id" element={<ListingManagementDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("Record sale");
    fireEvent.change(screen.getByLabelText(/Sale price/i), { target: { value: "45" } });
    fireEvent.click(screen.getByRole("button", { name: "Record sale" }));
    expect(soldSpy).toHaveBeenCalled();
  });
});
