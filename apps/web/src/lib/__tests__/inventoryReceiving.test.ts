import { describe, expect, it } from "vitest";

import type { InventoryItem } from "../../api/client";
import {
  canQuickReceiveInventoryCopy,
  countNewlyMarkedFromBulk,
  summaryAfterReceiveMarked,
} from "../inventoryReceiving";

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

describe("summaryAfterReceiveMarked", () => {
  it("moves counts from ordered to in hand", () => {
    const next = summaryAfterReceiveMarked(
      {
        total_copies: 5,
        in_hand_copies: 2,
        ordered_not_received_copies: 3,
        preordered_copies: 0,
        cancelled_copies: 0,
        total_cost_basis: "0",
        total_current_fmv: "0",
        total_unrealized_gain_loss: "0",
        raw_count: 5,
        graded_count: 0,
        hold_count: 5,
        sell_count: 0,
      },
      2,
    );
    expect(next?.in_hand_copies).toBe(4);
    expect(next?.ordered_not_received_copies).toBe(1);
  });
});

describe("countNewlyMarkedFromBulk", () => {
  it("ignores idempotent already_received rows", () => {
    expect(
      countNewlyMarkedFromBulk({
        marked_count: 2,
        skipped_count: 0,
        error_count: 0,
        results: [
          { inventory_copy_id: 1, outcome: "marked", detail: "already_received" },
          { inventory_copy_id: 2, outcome: "marked" },
        ],
      }),
    ).toBe(1);
  });
});
