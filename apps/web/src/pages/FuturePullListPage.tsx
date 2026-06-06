import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P81FuturePullListItemRead } from "../api/client";
import { DiscoveryNav } from "../components/discovery/p81/DiscoveryNav";
import { StatusBanner } from "../components/StatusBanner";

export function FuturePullListPage(): JSX.Element {
  const [items, setItems] = useState<P81FuturePullListItemRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.getFuturePullList({ refresh: true, limit: 50 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load future pull list.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-violet-300">P81-02</p>
          <h1 className="text-xl font-semibold">Future pull list</h1>
          <DiscoveryNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-3 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {items.length === 0 ? (
          <p className="text-slate-500">No future opportunities yet.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((p) => (
              <li key={p.id} className="rounded-xl border border-slate-700 bg-slate-900/40 p-3">
                <p className="font-medium text-white">{p.title}</p>
                <p className="text-xs text-slate-500">
                  {p.pipeline_status} · {p.watch_level} watch · Score {p.personalized_score.toFixed(0)}
                </p>
                <p className="mt-1 text-sm text-emerald-200">
                  {p.recommendation_action}
                  {p.recommendation_quantity > 0 ? ` ${p.recommendation_quantity}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
