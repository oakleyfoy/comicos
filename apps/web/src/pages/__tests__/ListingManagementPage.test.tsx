import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { ListingManagementPage } from "../ListingManagementPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const row: clientModule.P89ManagedListingRead = {
  id: 1,
  owner_user_id: 1,
  inventory_copy_id: 10,
  listing_draft_id: null,
  marketplace: "EBAY",
  listing_url: "",
  external_listing_id: "",
  title: "Spider-Man #1",
  comic_title: "Spider-Man #1",
  asking_price: 30,
  shipping_price: 5,
  minimum_price: 25,
  status: "DRAFT",
  listed_at: "2026-06-01T12:00:00Z",
  sold_at: null,
  expired_at: null,
  archived_at: null,
  sale_price: null,
  shipping_charged: null,
  marketplace_fees: null,
  shipping_cost: null,
  net_profit: null,
  notes: "",
  profit: null,
  status_history: [],
  inventory_auto_updated: false,
  created_at: "2026-06-01T12:00:00Z",
  updated_at: "2026-06-01T12:00:00Z",
};

describe("ListingManagementPage", () => {
  it("renders tabs and listing row", async () => {
    vi.spyOn(clientModule.apiClient, "listManagedListings").mockResolvedValue({
      items: [row],
      total_items: 1,
      limit: 100,
      offset: 0,
    });
    render(
      <MemoryRouter>
        <ListingManagementPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("Listing Management")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Spider-Man #1")).toBeInTheDocument();
    expect(screen.getByText("Mark Active")).toBeInTheDocument();
  });
});
