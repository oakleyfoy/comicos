import { useState } from "react";
import type { FormEvent } from "react";

import type { LiveSaleClaimCreateRequest } from "../../../api/client";

export function LiveSaleClaimForm({
  canManage,
  submitting,
  onSubmit,
}: {
  canManage: boolean;
  submitting: boolean;
  onSubmit: (payload: LiveSaleClaimCreateRequest) => Promise<void>;
}): JSX.Element {
  const [liveSaleQueueItemId, setLiveSaleQueueItemId] = useState("");
  const [buyerIdentifier, setBuyerIdentifier] = useState("");
  const [claimedPrice, setClaimedPrice] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    await onSubmit({
      live_sale_queue_item_id: Number(liveSaleQueueItemId),
      buyer_identifier: buyerIdentifier.trim(),
      claimed_status: "claimed",
      claimed_price: claimedPrice.trim() ? claimedPrice.trim() : null,
    });
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Claim shell</p>
      <h2 className="mt-1 text-base font-semibold text-white">Track buyer claims</h2>
      <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Queue item id</span>
            <input
              type="number"
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={liveSaleQueueItemId}
              onChange={(event) => setLiveSaleQueueItemId(event.target.value)}
            />
          </label>
          <label className="grid gap-1 md:col-span-2">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Buyer identifier</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={buyerIdentifier}
              onChange={(event) => setBuyerIdentifier(event.target.value)}
              placeholder="user123"
            />
          </label>
        </div>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Claimed price</span>
          <input
            type="text"
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={claimedPrice}
            onChange={(event) => setClaimedPrice(event.target.value)}
            placeholder="20.00"
          />
        </label>
        <button
          type="submit"
          disabled={!canManage || submitting}
          className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Creating..." : "Create claim"}
        </button>
      </form>
    </section>
  );
}
