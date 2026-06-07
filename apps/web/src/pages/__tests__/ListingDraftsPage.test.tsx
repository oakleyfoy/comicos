import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { ListingDraftsPage } from "../ListingDraftsPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const draft: clientModule.P89ListingDraftRead = {
  id: 1,
  owner_user_id: 1,
  inventory_copy_id: 10,
  sell_candidate_id: null,
  market_price_snapshot_id: null,
  marketplace: "EBAY",
  title: "X-Men #1 VF/NM Marvel Comics",
  description: "Details:\n\n• Publisher: Marvel",
  condition_notes: "Raw book.",
  shipping_notes: "Gemini mailer, USPS Ground Advantage.",
  suggested_price: 425,
  minimum_price: 380,
  premium_price: 460,
  status: "DRAFT",
  comic_title: "X-Men #1",
  pricing_unavailable: false,
  full_listing_text: "Title:\nX-Men",
  created_at: "2026-06-08T00:00:00Z",
  updated_at: "2026-06-08T00:00:00Z",
};

describe("ListingDraftsPage", () => {
  it("renders draft list sections", async () => {
    vi.spyOn(clientModule.apiClient, "listListingDrafts").mockResolvedValue({
      items: [draft],
      total_items: 1,
      limit: 100,
      offset: 0,
    });
    render(
      <MemoryRouter>
        <ListingDraftsPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Listing Drafts", level: 1 })).toBeInTheDocument();
    });
    expect(screen.getByText("Drafts")).toBeInTheDocument();
    expect(screen.getByText("Review Draft")).toBeInTheDocument();
  });

  it("renders empty state", async () => {
    vi.spyOn(clientModule.apiClient, "listListingDrafts").mockResolvedValue({
      items: [],
      total_items: 0,
      limit: 100,
      offset: 0,
    });
    render(
      <MemoryRouter>
        <ListingDraftsPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("No listing drafts yet.")).toBeInTheDocument();
  });
});
