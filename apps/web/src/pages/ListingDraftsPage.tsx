import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P78ListingDraftRead } from "../api/client";
import { SellWorkflowNav } from "../components/sell/p78/SellWorkflowNav";
import { StatusBanner } from "../components/StatusBanner";

export function ListingDraftsPage(): JSX.Element {
  const [items, setItems] = useState<P78ListingDraftRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listListingDrafts({ limit: 50, offset: 0 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load drafts.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-amber-300">P78-01</p>
          <h1 className="text-xl font-semibold">Listing drafts</h1>
          <SellWorkflowNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {items.length === 0 ? (
          <p className="text-slate-500">No listing drafts yet. Create one from the sell queue.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((d) => (
              <li key={d.id} className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
                <div className="flex flex-wrap justify-between gap-2">
                  <div>
                    <p className="font-medium text-white">{d.title}</p>
                    <p className="text-xs uppercase tracking-wider text-slate-500">{d.status}</p>
                  </div>
                  <p className="text-sm text-emerald-200">${d.market_price.toFixed(2)} market</p>
                </div>
                <p className="mt-2 text-xs text-slate-400 line-clamp-3 whitespace-pre-wrap">{d.description}</p>
                <p className="mt-2 text-xs text-slate-500">
                  Quick ${d.quick_sale_price.toFixed(2)} · Premium ${d.premium_price.toFixed(2)} · Qty {d.suggested_sell_quantity}
                </p>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
