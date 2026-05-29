import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import type {
  MarketplaceAccountResponse,
  MarketplaceListingDraftResponse,
  MarketplacePriceRecommendationGenerateRequest,
} from "../../../api/client";

export function MarketplacePriceRecommendationGeneratorShell({
  accounts,
  listings,
  canManage,
  submitting,
  onGenerate,
}: {
  accounts: MarketplaceAccountResponse[];
  listings: MarketplaceListingDraftResponse[];
  canManage: boolean;
  submitting: boolean;
  onGenerate: (payload: MarketplacePriceRecommendationGenerateRequest) => Promise<void>;
}): JSX.Element {
  const defaultAccountId = accounts[0]?.id ?? 0;
  const defaultListingId = listings[0]?.id ?? 0;
  const [marketplaceAccountId, setMarketplaceAccountId] = useState(String(defaultAccountId));
  const [marketplaceListingDraftId, setMarketplaceListingDraftId] = useState(String(defaultListingId));
  const [recommendationType, setRecommendationType] = useState("suggested_price");
  const [currentListingPrice, setCurrentListingPrice] = useState("");
  const [floorPrice, setFloorPrice] = useState("");
  const [ceilingPrice, setCeilingPrice] = useState("");

  useEffect(() => {
    if (defaultAccountId > 0) {
      setMarketplaceAccountId(String(defaultAccountId));
    }
  }, [defaultAccountId]);

  useEffect(() => {
    if (defaultListingId > 0) {
      setMarketplaceListingDraftId(String(defaultListingId));
    }
  }, [defaultListingId]);

  const disabled = !canManage || submitting || accounts.length === 0 || listings.length === 0;
  const marketLabel = useMemo(() => `${accounts.length} accounts · ${listings.length} listings`, [accounts.length, listings.length]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (disabled) {
      return;
    }
    await onGenerate({
      marketplace_account_id: Number(marketplaceAccountId),
      marketplace_listing_draft_id: Number(marketplaceListingDraftId),
      recommendation_type: recommendationType.trim() || "suggested_price",
      current_listing_price: currentListingPrice.trim() ? currentListingPrice.trim() : null,
      floor_price: floorPrice.trim() ? floorPrice.trim() : null,
      ceiling_price: ceilingPrice.trim() ? ceilingPrice.trim() : null,
    });
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Recommendation shell</p>
          <h2 className="mt-1 text-base font-semibold text-white">Generate a marketplace-aware price recommendation</h2>
          <p className="mt-1 text-sm text-slate-400">{marketLabel}</p>
        </div>
        <p className="text-xs uppercase tracking-[0.16em] text-slate-500">No external repricing</p>
      </div>
      <form className="mt-4 grid gap-3" onSubmit={handleSubmit}>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Marketplace account</span>
          <select
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={marketplaceAccountId}
            onChange={(event) => setMarketplaceAccountId(event.target.value)}
          >
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className="grid gap-1">
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Listing draft</span>
          <select
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={marketplaceListingDraftId}
            onChange={(event) => setMarketplaceListingDraftId(event.target.value)}
          >
            {listings.map((listing) => (
              <option key={listing.id} value={listing.id}>
                {listing.listing_title}
              </option>
            ))}
          </select>
        </label>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Recommendation type</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={recommendationType}
              onChange={(event) => setRecommendationType(event.target.value)}
              placeholder="suggested_price"
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Current listing price</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={currentListingPrice}
              onChange={(event) => setCurrentListingPrice(event.target.value)}
              placeholder="12.99"
            />
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Floor price</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={floorPrice}
              onChange={(event) => setFloorPrice(event.target.value)}
              placeholder="9.99"
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Ceiling price</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={ceilingPrice}
              onChange={(event) => setCeilingPrice(event.target.value)}
              placeholder="19.99"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={disabled}
          className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Generating..." : "Generate recommendation"}
        </button>
      </form>
    </section>
  );
}
