import { useState } from "react";
import type { FormEvent } from "react";

import type { LiveSaleQueueItemCreateRequest } from "../../../api/client";

export function LiveSaleQueueItemForm({
  canManage,
  submitting,
  onSubmit,
}: {
  canManage: boolean;
  submitting: boolean;
  onSubmit: (payload: LiveSaleQueueItemCreateRequest) => Promise<void>;
}): JSX.Element {
  const [inventoryItemId, setInventoryItemId] = useState("");
  const [marketplaceListingDraftId, setMarketplaceListingDraftId] = useState("");
  const [plannedPrice, setPlannedPrice] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    await onSubmit({
      inventory_item_id: Number(inventoryItemId),
      marketplace_listing_draft_id: Number(marketplaceListingDraftId),
      planned_price: plannedPrice.trim() ? plannedPrice.trim() : null,
    });
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Queue add shell</p>
      <h2 className="mt-1 text-base font-semibold text-white">Attach inventory to the run-of-show</h2>
      <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Inventory item id</span>
            <input
              type="number"
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={inventoryItemId}
              onChange={(event) => setInventoryItemId(event.target.value)}
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Listing draft id</span>
            <input
              type="number"
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={marketplaceListingDraftId}
              onChange={(event) => setMarketplaceListingDraftId(event.target.value)}
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Planned price</span>
            <input
              type="text"
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={plannedPrice}
              onChange={(event) => setPlannedPrice(event.target.value)}
              placeholder="25.00"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={!canManage || submitting}
          className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Adding..." : "Add queue item"}
        </button>
      </form>
    </section>
  );
}
