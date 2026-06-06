import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P78SellingAnalyticsRead } from "../api/client";
import { SellWorkflowNav } from "../components/sell/p78/SellWorkflowNav";
import { StatusBanner } from "../components/StatusBanner";

export function SellingAnalyticsPage(): JSX.Element {
  const [analytics, setAnalytics] = useState<P78SellingAnalyticsRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setAnalytics(await apiClient.getSellingAnalytics());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load selling analytics.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!analytics) {
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
          <p className="text-[11px] uppercase tracking-[0.2em] text-amber-300">P78-02</p>
          <h1 className="text-xl font-semibold">Selling analytics</h1>
          <SellWorkflowNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

        <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
            <p className="text-xs uppercase text-slate-500">Revenue</p>
            <p className="mt-1 text-lg font-semibold text-white">${analytics.revenue.toFixed(0)}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
            <p className="text-xs uppercase text-slate-500">Profit</p>
            <p className="mt-1 text-lg font-semibold text-emerald-200">${analytics.profit.toFixed(0)}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
            <p className="text-xs uppercase text-slate-500">ROI</p>
            <p className="mt-1 text-lg font-semibold text-white">{analytics.roi_pct.toFixed(0)}%</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
            <p className="text-xs uppercase text-slate-500">Listings created</p>
            <p className="mt-1 text-lg font-semibold text-white">{analytics.listings_created}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
            <p className="text-xs uppercase text-slate-500">Listings sold</p>
            <p className="mt-1 text-lg font-semibold text-white">{analytics.listings_sold}</p>
          </div>
          <div className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
            <p className="text-xs uppercase text-slate-500">Sell conversion</p>
            <p className="mt-1 text-lg font-semibold text-white">{analytics.sell_conversion_rate_pct.toFixed(1)}%</p>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4 text-sm text-slate-300">
          <p>
            Average days to sell:{" "}
            {analytics.average_days_to_sell != null ? analytics.average_days_to_sell.toFixed(1) : "—"}
          </p>
          {analytics.sell_recommendation_accuracy_pct != null ? (
            <p className="mt-2">Sell recommendation accuracy: {analytics.sell_recommendation_accuracy_pct.toFixed(1)}%</p>
          ) : null}
        </section>
      </main>
    </div>
  );
}
