import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P82MarketplaceAcquisitionOpportunityRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { CollectorEmptyState } from "../components/CollectorEmptyState";
import { CollectorErrorState } from "../components/CollectorErrorState";

export function MarketplaceOpportunitiesPage(): JSX.Element {
  const [items, setItems] = useState<P82MarketplaceAcquisitionOpportunityRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listMarketplaceAcquisitionOpportunities({ refresh: false, limit: 50 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load opportunities.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-violet-300">P82</p>
          <h1 className="text-xl font-semibold">Marketplace opportunities</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-6">
        {error ? <CollectorErrorState message={error} onRetry={() => void load()} /> : null}
        {items.length === 0 && !error ? (
          <CollectorEmptyState
            title="No marketplace opportunities yet"
            description="Refresh deals from your inventory FMV spread or scan an eBay listing."
            actionLabel="Acquisition dashboard"
            actionTo="/marketplace-acquisition-dashboard"
          />
        ) : null}
        <ul className="space-y-2 text-sm">
          {items.map((o) => (
            <li key={o.id} className="rounded border border-slate-800 p-3">
              <Link to={`/marketplace-opportunity/${o.id}`} className="font-medium text-amber-200 hover:underline">
                {o.title}
              </Link>
              <p className="text-slate-400">
                {o.recommendation} · score {o.opportunity_score.toFixed(0)} · ${o.asking_price.toFixed(2)} vs FMV $
                {o.estimated_fmv.toFixed(2)}
              </p>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
