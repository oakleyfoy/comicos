import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

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
    expect(screen.getByRole("button", { name: "Mark Reviewed" })).toBeInTheDocument();
    fireEvent.change(screen.getByDisplayValue("Amazing Spider-Man #300"), {
      target: { value: "Updated Title" },
    });
    expect(screen.getByDisplayValue("Updated Title")).toBeInTheDocument();
  });
});
