import { useState, type FormEvent } from "react";

import type {
  MarketplaceAccountResponse,
  MarketplaceListingDraftCreateRequest,
} from "../../../api/client";

type Props = {
  accounts: MarketplaceAccountResponse[];
  defaultInventoryItemId?: number | null;
  submitting: boolean;
  onSubmit: (payload: MarketplaceListingDraftCreateRequest) => Promise<void>;
};

export function MarketplaceListingDraftForm({
  accounts,
  defaultInventoryItemId,
  submitting,
  onSubmit,
}: Props): JSX.Element {
  const connected = accounts.filter((row) => row.account_status === "connected");
  const [marketplaceAccountId, setMarketplaceAccountId] = useState<number>(connected[0]?.id ?? 0);
  const [inventoryItemId, setInventoryItemId] = useState(String(defaultInventoryItemId ?? ""));
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [price, setPrice] = useState("");
  const [quantity, setQuantity] = useState("1");

  async function handleSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!marketplaceAccountId || !inventoryItemId.trim() || !title.trim()) {
      return;
    }
    await onSubmit({
      marketplace_account_id: marketplaceAccountId,
      inventory_item_id: Number(inventoryItemId),
      listing_title: title.trim(),
      listing_description: description.trim() || null,
      listing_price: price.trim() || null,
      listing_currency: "USD",
      listing_quantity: Number(quantity) || 1,
    });
    setTitle("");
    setDescription("");
    setPrice("");
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="space-y-3 rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Create listing draft</p>
      <label className="block text-sm text-slate-300">
        Marketplace account
        <select
          className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2"
          value={marketplaceAccountId}
          onChange={(event) => setMarketplaceAccountId(Number(event.target.value))}
        >
          {connected.map((row) => (
            <option key={row.id} value={row.id}>
              {row.display_name} ({row.marketplace_type})
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm text-slate-300">
        Inventory copy id
        <input
          className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2 font-mono text-sm"
          value={inventoryItemId}
          onChange={(event) => setInventoryItemId(event.target.value)}
        />
      </label>
      <label className="block text-sm text-slate-300">
        Title
        <input className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2" value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="block text-sm text-slate-300">
        Description
        <textarea className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2" rows={3} value={description} onChange={(event) => setDescription(event.target.value)} />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-sm text-slate-300">
          Price
          <input className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2" value={price} onChange={(event) => setPrice(event.target.value)} />
        </label>
        <label className="block text-sm text-slate-300">
          Quantity
          <input className="mt-1 w-full rounded-xl border border-white/10 bg-slate-900 px-3 py-2" value={quantity} onChange={(event) => setQuantity(event.target.value)} />
        </label>
      </div>
      <button
        type="submit"
        disabled={submitting || !connected.length}
        className="rounded-xl bg-indigo-500 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {submitting ? "Saving…" : "Create draft"}
      </button>
    </form>
  );
}
