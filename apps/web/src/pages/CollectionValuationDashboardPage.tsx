import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P83CollectionValuationDashboardRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectionValuationDashboardPage(): JSX.Element {
  const [dash, setDash] = useState<P83CollectionValuationDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDash(await apiClient.getCollectionValuationDashboard());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load valuation dashboard.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!dash) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : <p className="text-slate-400">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-emerald-300">P83</p>
          <h1 className="text-xl font-semibold">Collection valuation dashboard</h1>
          <CollectorExpansionNav />
          <p className="text-sm text-slate-400">
            <Link to="/collection-forecast" className="text-violet-300 hover:underline">
              Forecast
            </Link>
            {" · "}
            <Link to="/collection-risk" className="text-violet-300 hover:underline">
              Risk
            </Link>
            {" · "}
            <Link to="/collection-scenarios" className="text-violet-300 hover:underline">
              Scenarios
            </Link>
            {" · "}
            <Link to="/collection-optimization" className="text-violet-300 hover:underline">
              Optimization
            </Link>
          </p>
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-6 text-sm">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <p>
          Current value ${dash.forecast.current_value.toFixed(2)} · Risk {dash.risk.risk_category} (
          {dash.risk.risk_score.toFixed(0)})
        </p>
        <section>
          <h2 className="font-semibold">Buy targets</h2>
          <ul className="mt-2 text-slate-300">
            {dash.optimization.buy_targets.map((b, i) => (
              <li key={i}>{String(b.title ?? "—")}</li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
