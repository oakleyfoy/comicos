import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { ListingDraftReviewPage } from "../ListingDraftReviewPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const draft: clientModule.P89ListingDraftRead = {
  id: 5,
  owner_user_id: 1,
  inventory_copy_id: 10,
  sell_candidate_id: null,
  market_price_snapshot_id: null,
  marketplace: "EBAY",
  title: "Amazing Spider-Man #300",
  description: "First full appearance of Venom.",
  condition_notes: "Raw comic.",
  shipping_notes: "Gemini mailer.",
  suggested_price: 425,
  minimum_price: 380,
  premium_price: 460,
  status: "DRAFT",
  comic_title: "Amazing Spider-Man #300",
  pricing_unavailable: false,
  full_listing_text: "Title:\nAmazing Spider-Man #300",
  created_at: "2026-06-08T00:00:00Z",
  updated_at: "2026-06-08T00:00:00Z",
};

describe("ListingDraftReviewPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders editable fields and copy actions", async () => {
    vi.spyOn(clientModule.apiClient, "getListingDraft").mockResolvedValue(draft);
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
    render(
      <MemoryRouter initialEntries={["/listing-drafts/5"]}>
        <Routes>
          <Route path="/listing-drafts/:id" element={<ListingDraftReviewPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByDisplayValue("Amazing Spider-Man #300")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Copy Title" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Managed Listing" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark Reviewed" })).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("Amazing Spider-Man #300"), {
      target: { value: "Updated Title" },
    });
    expect(screen.getByDisplayValue("Updated Title")).toBeInTheDocument();
  });

  it("creates managed listing from draft", async () => {
    vi.spyOn(clientModule.apiClient, "getListingDraft").mockResolvedValue(draft);
    const createSpy = vi.spyOn(clientModule.apiClient, "createManagedListing").mockResolvedValue({
      id: 99,
      owner_user_id: 1,
      inventory_copy_id: 10,
      listing_draft_id: 5,
      marketplace: "EBAY",
      listing_url: "",
      external_listing_id: "",
      title: draft.title,
      comic_title: draft.comic_title,
      asking_price: 425,
      shipping_price: null,
      minimum_price: 380,
      status: "DRAFT",
      listed_at: null,
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
      created_at: draft.created_at,
      updated_at: draft.updated_at,
    });
    render(
      <MemoryRouter initialEntries={["/listing-drafts/5"]}>
        <Routes>
          <Route path="/listing-drafts/:id" element={<ListingDraftReviewPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Create Managed Listing" })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Managed Listing" }));
    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith({ listing_draft_id: 5 });
    });
  });
});
