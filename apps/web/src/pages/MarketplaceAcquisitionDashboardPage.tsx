import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P82MarketplaceAcquisitionDashboardRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

function Section({ title, items }: { title: string; items: { id: number; title: string; opportunity_score: number }[] }) {
  return (
    <section>
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <ul className="mt-2 space-y-1 text-sm text-slate-300">
        {items.map((i) => (
          <li key={i.id}>
            <Link to={`/marketplace-opportunity/${i.id}`} className="text-amber-200 hover:underline">
              {i.title}
            </Link>{" "}
            ({i.opportunity_score.toFixed(0)})
          </li>
        ))}
      </ul>
    </section>
  );
}

export function MarketplaceAcquisitionDashboardPage(): JSX.Element {
  const [dash, setDash] = useState<P82MarketplaceAcquisitionDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDash(await apiClient.getMarketplaceAcquisitionDashboard({ refresh: true }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load dashboard.");
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
          <h1 className="text-xl font-semibold">Marketplace acquisition dashboard</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl grid gap-6 px-4 py-6 md:grid-cols-2">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <Section title="Strong buys" items={dash.strong_buys} />
        <Section title="Good buys" items={dash.good_buys} />
        <Section title="Watch" items={dash.watch} />
        <Section title="Largest FMV spread" items={dash.largest_spread} />
        <Section title="Best grading upside" items={dash.best_grading_upside} />
        <Section title="Best profile matches" items={dash.best_profile_matches} />
      </main>
    </div>
  );
}
