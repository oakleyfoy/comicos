import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P81DiscoveryAnalyticsDashboardRead } from "../api/client";
import { DiscoveryNav } from "../components/discovery/p81/DiscoveryNav";
import { StatusBanner } from "../components/StatusBanner";

export function DiscoveryAnalyticsPage(): JSX.Element {
  const [dash, setDash] = useState<P81DiscoveryAnalyticsDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDash(await apiClient.getDiscoveryAnalyticsDashboard({ refresh: true }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load discovery analytics.");
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

  const act = dash.activity;
  const pers = dash.personalization_impact;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-violet-300">P81-03</p>
          <h1 className="text-xl font-semibold">Discovery analytics</h1>
          <DiscoveryNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

        <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-700 p-3">
            <p className="text-xs text-slate-500">Discovered</p>
            <p className="text-lg font-semibold">{act.opportunities_discovered}</p>
          </div>
          <div className="rounded-xl border border-slate-700 p-3">
            <p className="text-xs text-slate-500">Viewed</p>
            <p className="text-lg font-semibold">{act.opportunities_viewed}</p>
          </div>
          <div className="rounded-xl border border-slate-700 p-3">
            <p className="text-xs text-slate-500">Saved</p>
            <p className="text-lg font-semibold">{act.opportunities_saved}</p>
          </div>
        </section>

        <section className="rounded-xl border border-slate-700 p-4">
          <h2 className="text-sm font-semibold">Opportunity performance</h2>
          <ul className="mt-2 space-y-1 text-sm text-slate-300">
            {dash.opportunity_performance.map((c) => (
              <li key={c.category}>
                {c.category}: {c.detected} detected · {c.purchased} purchased · {c.conversion_rate_pct}%
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-xl border border-slate-700 p-4 text-sm text-slate-300">
          <p>
            Alerts: {dash.alert_performance.alerts_sent} sent · {dash.alert_performance.alerts_opened} opened ·{" "}
            {dash.alert_performance.alerts_converted} converted
          </p>
          <p className="mt-2">
            Future pull: {dash.future_pull.recommendations} recs · {dash.future_pull.purchased} purchased ·{" "}
            {dash.future_pull.accuracy_pct}% accuracy
          </p>
          <p className="mt-2">Discovery portfolio ROI: {dash.discovery_roi.portfolio_roi_pct}%</p>
          <p className="mt-2">
            Personalization: {pers.opportunities_evaluated} evaluated · {pers.adjustment_rate_pct}% adjusted
          </p>
        </section>
      </main>
    </div>
  );
}
