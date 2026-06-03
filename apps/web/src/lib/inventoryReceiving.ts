import type { BulkMarkInventoryReceivedResponse, InventoryItem, InventorySummary } from "../api/client";

/** Copies eligible for list quick-receive (shipment intake). */
export function canQuickReceiveInventoryCopy(item: InventoryItem): boolean {
  if (item.asset_state !== "ordered_not_received") {
    return false;
  }
  if (item.order_status === "cancelled" || item.hold_status === "sold") {
    return false;
  }
  return true;
}

export function mergeInventoryRowsAfterReceive(
  current: InventoryItem[],
  rows: Iterable<InventoryItem | null | undefined>,
): InventoryItem[] {
  const byId = new Map<number, InventoryItem>();
  for (const row of rows) {
    if (row?.inventory_copy_id != null) {
      byId.set(row.inventory_copy_id, row);
    }
  }
  if (!byId.size) {
    return current;
  }
  return current.map((item) => {
    const updated = byId.get(item.inventory_copy_id);
    return updated ? { ...item, ...updated } : item;
  });
}

/** Adjust portfolio summary cards after copies move to in-hand (no full dashboard reload). */
export function summaryAfterReceiveMarked(
  summary: InventorySummary | null,
  newlyMarkedCount: number,
): InventorySummary | null {
  if (!summary || newlyMarkedCount <= 0) {
    return summary;
  }
  return {
    ...summary,
    in_hand_copies: summary.in_hand_copies + newlyMarkedCount,
    ordered_not_received_copies: Math.max(0, summary.ordered_not_received_copies - newlyMarkedCount),
  };
}

export function countNewlyMarkedFromBulk(response: BulkMarkInventoryReceivedResponse): number {
  return response.results.filter(
    (r) => r.outcome === "marked" && r.detail !== "already_received",
  ).length;
}
