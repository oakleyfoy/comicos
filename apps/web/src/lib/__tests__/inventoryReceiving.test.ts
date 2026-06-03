import { describe, expect, it } from "vitest";

import type { InventoryItem } from "../../api/client";
import { canQuickReceiveInventoryCopy } from "../inventoryReceiving";

function item(partial: Partial<InventoryItem>): InventoryItem {
  return {
    inventory_copy_id: 1,
    title: "Test",
    publisher: "Marvel",
    issue_number: "1",
    cover_name: null,
    printing: null,
    ratio: null,
    variant_type: null,
    cover_artist: null,
    retailer: "LCS",
    order_date: "2026-01-01",
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
    release_status: "released",
    order_status: "ordered",
    asset_state: "ordered_not_received",
    is_in_hand: false,
    ...partial,
  } as InventoryItem;
}

describe("canQuickReceiveInventoryCopy", () => {
  it("allows released orders not yet received", () => {
    expect(canQuickReceiveInventoryCopy(item({}))).toBe(true);
  });

  it("blocks in-hand, cancelled, and sold copies", () => {
    expect(canQuickReceiveInventoryCopy(item({ asset_state: "in_hand", order_status: "received" }))).toBe(
      false,
    );
    expect(
      canQuickReceiveInventoryCopy(item({ asset_state: "cancelled", order_status: "cancelled" })),
    ).toBe(false);
    expect(canQuickReceiveInventoryCopy(item({ hold_status: "sold" }))).toBe(false);
  });
});
