import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P81DiscoveryWatchlistRead } from "../api/client";
import { DiscoveryNav } from "../components/discovery/p81/DiscoveryNav";
import { StatusBanner } from "../components/StatusBanner";

export function DiscoveryWatchlistsPage(): JSX.Element {
  const [items, setItems] = useState<P81DiscoveryWatchlistRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [label, setLabel] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listDiscoveryWatchlists();
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load watchlists.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const addSeries = async () => {
    if (!label.trim()) return;
    try {
      await apiClient.createDiscoveryWatchlist({ watchlist_type: "SERIES", label: label.trim() });
      setLabel("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add watchlist.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-violet-300">P81-02</p>
          <h1 className="text-xl font-semibold">Discovery watchlists</h1>
          <DiscoveryNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-4 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
            placeholder="Series to watch"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
          <button type="button" className="rounded-lg bg-violet-600 px-3 py-2 text-sm" onClick={() => void addSeries()}>
            Add
          </button>
        </div>
        <ul className="space-y-2">
          {items.map((w) => (
            <li key={w.id} className="flex justify-between rounded-lg border border-slate-700 px-3 py-2 text-sm">
              <span>
                {w.label} <span className="text-slate-500">({w.watchlist_type})</span>
              </span>
              <span className="text-xs text-slate-500">{w.auto_managed ? "Auto" : "Manual"} · {w.active ? "On" : "Off"}</span>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
