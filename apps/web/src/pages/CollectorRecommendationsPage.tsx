import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P77PersonalizedRecommendationRead } from "../api/client";
import { CollectorProfileNav } from "../components/collector/p77/CollectorProfileNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectorRecommendationsPage(): JSX.Element {
  const [items, setItems] = useState<P77PersonalizedRecommendationRead[]>([]);
  const [estimatedSpend, setEstimatedSpend] = useState<number | null>(null);
  const [filteredCount, setFilteredCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listPersonalizedRecommendations({ limit: 40, offset: 0 });
      setItems(body.items);
      setEstimatedSpend(body.estimated_spend ?? null);
      setFilteredCount(body.budget_filtered_count ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load recommendations.");
    }
  }, []);

  useEffect(() => {
    void load();
    void apiClient.markRecommendationsViewed().catch(() => undefined);
  }, [load]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-3xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-sky-300">P77-02</p>
          <h1 className="text-xl font-semibold">Personalized recommendations</h1>
          <CollectorProfileNav />
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {estimatedSpend != null ? (
          <p className="text-sm text-slate-400">
            Estimated spend (shown set): ${estimatedSpend.toFixed(2)}
            {filteredCount != null ? ` · ${filteredCount} items after budget filter` : ""}
          </p>
        ) : null}
        {items.length === 0 ? (
          <p className="text-slate-400">No personalized recommendations yet.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((row, idx) => (
              <li key={`${row.source}-${row.title}-${idx}`} className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <p className="font-medium text-white">{row.title}</p>
                    {row.subtitle ? <p className="text-sm text-slate-400">{row.subtitle}</p> : null}
                    <p className="mt-1 text-xs uppercase tracking-wider text-slate-500">{row.source}</p>
                  </div>
                  <p className="text-2xl font-bold text-sky-200">{row.personalized_score.toFixed(0)}</p>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Global {row.global_score.toFixed(0)} · adjustment {row.collector_adjustment > 0 ? "+" : ""}
                  {row.collector_adjustment.toFixed(0)}
                  {row.budget_impact ? ` · budget impact $${row.budget_impact.toFixed(0)}` : ""}
                </p>
                {row.reasons.length ? (
                  <ul className="mt-2 space-y-1 text-sm text-slate-300">
                    {row.reasons.slice(0, 5).map((r) => (
                      <li key={r}>• {r}</li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
