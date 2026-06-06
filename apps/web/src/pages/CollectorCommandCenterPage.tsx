import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P84CollectorCommandCenterRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectorCommandCenterPage(): JSX.Element {
  const [cc, setCc] = useState<P84CollectorCommandCenterRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setCc(await apiClient.getCollectorCommandCenter());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load command center.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!cc) {
    return (
      <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : <p className="text-slate-400">Loading…</p>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-5xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-amber-300">P82–P84</p>
          <h1 className="text-xl font-semibold">Collector command center</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-5xl grid gap-6 px-4 py-6 md:grid-cols-2 lg:grid-cols-3 text-sm">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <section className="rounded border border-slate-800 p-4">
          <h2 className="font-semibold">Marketplace deals</h2>
          <ul className="mt-2 text-slate-300">
            {cc.marketplace_deals.slice(0, 5).map((d) => (
              <li key={d.id}>
                <Link to={`/marketplace-opportunity/${d.id}`} className="text-amber-200 hover:underline">
                  {d.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded border border-slate-800 p-4">
          <h2 className="font-semibold">Collection forecast</h2>
          <p className="mt-2 text-slate-300">
            ${cc.collection_forecast?.current_value.toFixed(2) ?? "—"}
          </p>
        </section>
        <section className="rounded border border-slate-800 p-4">
          <h2 className="font-semibold">Budget</h2>
          <p className="mt-2 text-slate-300">{String(cc.budget_status.state ?? "—")}</p>
        </section>
        <section className="rounded border border-slate-800 p-4 md:col-span-2">
          <h2 className="font-semibold">Daily briefing actions</h2>
          <ul className="mt-2 list-disc pl-5 text-slate-300">
            {cc.daily_briefing?.top_actions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
