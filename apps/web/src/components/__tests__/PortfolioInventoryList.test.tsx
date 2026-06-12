import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { PortfolioInventoryList } from "../PortfolioInventoryList";
import type { InventoryItem } from "../../api/client";

function makeItem(overrides: Partial<InventoryItem>): InventoryItem {
  return {
    inventory_copy_id: 1,
    title: "Batman",
    publisher: "DC",
    issue_number: "1",
    cover_name: null,
    printing: null,
    ratio: null,
    variant_type: null,
    cover_artist: null,
    retailer: "Midtown Comics",
    order_date: "2026-06-11",
    acquisition_cost: "4.99",
    current_fmv: null,
    current_market_fmv: null,
    fmv_snapshot_id: null,
    fmv_method: null,
    fmv_confidence_bucket: null,
    fmv_liquidity_bucket: null,
    fmv_volatility_bucket: null,
    fmv_stale_data: null,
    fmv_currency_code: null,
    valuation_scope: null,
    valuation_evidence_json: null,
    gain_loss: null,
    grade_status: "raw",
    hold_status: "hold",
    star_rating: null,
    condition_notes: null,
    release_status: "unknown",
    order_status: "shipped",
    asset_state: "ordered_not_received",
    is_in_hand: false,
    ...overrides,
  } as InventoryItem;
}

function renderList(items: InventoryItem[]): void {
  render(
    <MemoryRouter>
      <PortfolioInventoryList
        inventory={items}
        selectedIds={[]}
        isSaving={false}
        fMvDrafts={{}}
        gradeDrafts={{}}
        holdDrafts={{}}
        starDrafts={{}}
        normalizeDecimalInput={(v) => v}
        onToggleSelection={() => {}}
        onFmvDraftChange={() => {}}
        onGradeDraftChange={() => {}}
        onHoldDraftChange={() => {}}
        onStarDraftChange={() => {}}
        onSave={async () => {}}
        onOpenNotes={() => {}}
        receivingCopyIds={new Set()}
        onMarkReceived={() => {}}
      />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("PortfolioInventoryList cover thumbnails", () => {
  it("renders the cover image when a cover_image_url is present", () => {
    renderList([
      makeItem({ inventory_copy_id: 5, cover_image_url: "/files/cover-images/42", cover_source: "catalog_cover" }),
    ]);
    const img = screen.getByAltText("");
    expect(img).toBeTruthy();
    expect(img.getAttribute("src")).toBe("/files/cover-images/42");
  });

  it("renders a placeholder when no cover image is available", () => {
    renderList([makeItem({ inventory_copy_id: 6, cover_image_url: null, cover_source: "placeholder" })]);
    const cover = screen.getByTestId("inventory-card-cover");
    expect(cover).toBeTruthy();
    expect(cover.querySelector("img")).toBeNull();
  });
});
