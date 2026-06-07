import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P81DiscoveryWatchlistRead } from "../api/client";
import { DiscoveryPageLayout, PatriotPanel } from "../components/discovery/p81/DiscoveryPageLayout";
import { patriotInputClass, patriotPrimaryButtonClass } from "../components/patriotTheme";

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
    <DiscoveryPageLayout title="Discovery watchlists" error={error} onRetry={() => void load()}>
      <PatriotPanel>
        <div className="flex gap-2">
          <input className={`flex-1 ${patriotInputClass}`} placeholder="Series to watch" value={label} onChange={(e) => setLabel(e.target.value)} />
          <button type="button" className={patriotPrimaryButtonClass} onClick={() => void addSeries()}>
            Add
          </button>
        </div>
      </PatriotPanel>
      <ul className="space-y-2">
        {items.map((w) => (
          <li key={w.id} className="flex justify-between rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-blue-950">
            <span>
              {w.label} <span className="text-blue-800/70">({w.watchlist_type})</span>
            </span>
            <span className="text-xs text-blue-800/70">
              {w.auto_managed ? "Auto" : "Manual"} · {w.active ? "On" : "Off"}
            </span>
          </li>
        ))}
      </ul>
    </DiscoveryPageLayout>
  );
}
