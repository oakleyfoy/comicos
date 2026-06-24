import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as intake from "../../../api/intake";
import { IntakeReviewPage } from "../IntakeReviewPage";

function renderReview() {
  return render(
    <MemoryRouter initialEntries={["/intake/review/tok-1"]}>
      <Routes>
        <Route path="/intake/review/:token" element={<IntakeReviewPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const baseReview = {
  session: {
    id: 1,
    session_token: "tok-1",
    name: null,
    status: "active",
    source_device: null,
    scanned_count: 3,
    created_at: "2026-06-24T00:00:00Z",
    expires_at: "2026-06-25T00:00:00Z",
    last_seen_at: null,
    scanner_url: "/intake/scan/tok-1",
    review_url: "/intake/review/tok-1",
  },
  counts: {
    scanned: 3,
    queued: 1,
    processing: 0,
    auto_matched: 1,
    ready_for_review: 1,
    needs_review: 0,
    added_to_inventory: 0,
    rejected: 0,
    failed: 0,
  },
  items: [
    {
      id: 11,
      session_id: 1,
      status: "ready_for_review",
      confidence: 0.8,
      match_source: "comicvine",
      raw_barcode: "76194134192703921",
      normalized_barcode: "76194134192703921",
      base_upc: "761941341927",
      extension: "03921",
      selected_catalog_issue_id: 500,
      selected_variant_id: null,
      matched_publisher: "DC Comics",
      matched_series: "Superman",
      matched_issue_number: "39",
      matched_year: "2015",
      cover_url: null,
      reason: null,
      error: null,
      image_url: "/api/v1/intake/sessions/tok-1/items/11/image",
      acquisition_id: null,
      inventory_copy_id: null,
      created_at: "2026-06-24T00:00:00Z",
      processed_at: "2026-06-24T00:01:00Z",
      candidates: [],
    },
  ],
};

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("IntakeReviewPage", () => {
  it("shows live counts and item details", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue(baseReview);
    renderReview();
    expect(await screen.findByTestId("count-auto_matched")).toHaveTextContent("1");
    expect(screen.getByTestId("count-ready_for_review")).toHaveTextContent("1");
    expect(screen.getByText("Superman #39")).toBeInTheDocument();
  });

  it("adds an item to inventory", async () => {
    vi.spyOn(intake, "getIntakeReview").mockResolvedValue(baseReview);
    const addSpy = vi.spyOn(intake, "addIntakeItemToInventory").mockResolvedValue({
      ...baseReview.items[0],
      status: "added_to_inventory",
      inventory_copy_id: 99,
    });
    renderReview();
    const addButton = await screen.findByRole("button", { name: "Add to inventory" });
    fireEvent.click(addButton);
    await waitFor(() => expect(addSpy).toHaveBeenCalledWith(11));
  });
});
