import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import type { MarketplaceAccountResponse, ShopifyStorefrontCreateRequest } from "../../../api/client";

export function ShopifyStorefrontForm({
  accounts,
  canManage,
  submitting,
  onSubmit,
}: {
  accounts: MarketplaceAccountResponse[];
  canManage: boolean;
  submitting: boolean;
  onSubmit: (payload: ShopifyStorefrontCreateRequest) => Promise<void>;
}): JSX.Element {
  const defaultAccountId = accounts[0]?.id ?? 0;
  const [marketplaceAccountId, setMarketplaceAccountId] = useState(String(defaultAccountId));
  const [storefrontName, setStorefrontName] = useState("ComicOS Shopify");
  const [storefrontIdentifier, setStorefrontIdentifier] = useState("comicos-shopify");
  const [storefrontStatus, setStorefrontStatus] = useState("draft");

  useEffect(() => {
    if (defaultAccountId > 0) {
      setMarketplaceAccountId(String(defaultAccountId));
    }
  }, [defaultAccountId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    await onSubmit({
      marketplace_account_id: Number(marketplaceAccountId),
      storefront_name: storefrontName.trim(),
      storefront_identifier: storefrontIdentifier.trim(),
      storefront_status: storefrontStatus,
    });
  }

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Storefront registry</p>
      <h2 className="mt-1 text-base font-semibold text-white">Register a Shopify storefront</h2>
      <p className="mt-2 text-xs uppercase tracking-[0.16em] text-slate-500">No publish action is exposed</p>
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
          <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Storefront name</span>
          <input
            className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
            value={storefrontName}
            onChange={(event) => setStorefrontName(event.target.value)}
          />
        </label>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Storefront identifier</span>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={storefrontIdentifier}
              onChange={(event) => setStorefrontIdentifier(event.target.value)}
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs uppercase tracking-[0.16em] text-slate-500">Publication status</span>
            <select
              className="rounded-2xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100"
              value={storefrontStatus}
              onChange={(event) => setStorefrontStatus(event.target.value)}
            >
              <option value="draft">draft</option>
              <option value="ready">ready</option>
              <option value="published_internal">published_internal</option>
              <option value="unpublished_internal">unpublished_internal</option>
            </select>
          </label>
        </div>
        <button
          type="submit"
          disabled={!canManage || submitting || accounts.length === 0}
          className="rounded-2xl border border-violet-400/30 bg-violet-500/15 px-4 py-2 text-sm font-semibold text-violet-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Registering..." : "Create storefront"}
        </button>
      </form>
    </section>
  );
}
