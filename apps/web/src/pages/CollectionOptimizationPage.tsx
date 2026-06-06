import { useEffect, useState } from "react";

import { ApiError, apiClient, type P83CollectionValuationDashboardRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectionOptimizationPage(): JSX.Element {
  const [opt, setOpt] = useState<P83CollectionValuationDashboardRead["optimization"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const dash = await apiClient.getCollectionValuationDashboard();
        setOpt(dash.optimization);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load optimization.");
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl space-y-3">
          <h1 className="text-xl font-semibold">Portfolio optimization</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6 text-sm text-slate-300">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {opt ? (
          <>
            <p>Sell candidates: {opt.sell_candidates.length}</p>
            <p>Grade candidates: {opt.grade_candidates.length}</p>
            <p>Buy targets: {opt.buy_targets.length}</p>
          </>
        ) : (
          <p className="text-slate-400">Loading…</p>
        )}
      </main>
    </div>
  );
}
