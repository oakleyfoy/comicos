import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiClient, type P82MarketplaceAcquisitionOpportunityRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

export function MarketplaceOpportunityDetailPage(): JSX.Element {
  const { id } = useParams();
  const [opp, setOpp] = useState<P82MarketplaceAcquisitionOpportunityRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setError(null);
    try {
      setOpp(await apiClient.getMarketplaceAcquisitionOpportunity(Number(id)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Not found.");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!opp) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : <p className="text-slate-400">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl space-y-3">
          <Link to="/marketplace-opportunities" className="text-sm text-violet-300 hover:underline">
            ← Opportunities
          </Link>
          <h1 className="text-xl font-semibold">{opp.title}</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6 text-sm">
        <p>
          {opp.recommendation} · Score {opp.opportunity_score} · Discount to FMV {opp.discount_to_fmv}%
        </p>
        <ul className="list-disc pl-5 text-slate-300">
          {opp.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
        {opp.listing_url ? (
          <a href={opp.listing_url} className="text-violet-300 hover:underline" target="_blank" rel="noreferrer">
            View listing
          </a>
        ) : null}
      </main>
    </div>
  );
}
