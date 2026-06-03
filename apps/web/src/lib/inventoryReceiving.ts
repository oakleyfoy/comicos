import type { InventoryItem } from "../api/client";

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
