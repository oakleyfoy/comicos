import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P81PersonalizedDiscoveryDashboardRead } from "../api/client";
import { DiscoveryNav } from "../components/discovery/p81/DiscoveryNav";
import { StatusBanner } from "../components/StatusBanner";

export function DiscoveryDashboardPage(): JSX.Element {
  const [dash, setDash] = useState<P81PersonalizedDiscoveryDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDash(await apiClient.getDiscoveryDashboard({ refresh: true }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load discovery dashboard.");
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
          <p className="text-[11px] uppercase tracking-[0.2em] text-violet-300">P81-02</p>
          <h1 className="text-xl font-semibold">Discovery dashboard</h1>
          <DiscoveryNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <p className="text-sm text-slate-400">
          Must buy {dash.counts.must_buy ?? 0} · High {dash.counts.high_priority ?? 0} · Alerts{" "}
          {dash.counts.active_alerts ?? 0}
        </p>
        <section>
          <h2 className="text-sm font-semibold text-white">Must buy</h2>
          <ul className="mt-2 space-y-1 text-sm">
            {dash.must_buy.map((o) => (
              <li key={o.opportunity.id}>
                <Link to={`/discovery-opportunity/${o.opportunity.id}`} className="text-amber-200 hover:underline">
                  {o.opportunity.title} ({o.personalized_score.toFixed(0)})
                </Link>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="text-sm font-semibold text-white">Future pull list</h2>
          <ul className="mt-2 space-y-1 text-sm text-slate-300">
            {dash.future_pull_list.slice(0, 8).map((p) => (
              <li key={p.id}>
                {p.title} — {p.recommendation_action} {p.recommendation_quantity || ""} · {p.pipeline_status}
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="text-sm font-semibold text-white">Active alerts</h2>
          <ul className="mt-2 space-y-1 text-sm text-slate-400">
            {dash.active_alerts.map((a) => (
              <li key={a.id}>
                [{a.priority}] {a.title}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
