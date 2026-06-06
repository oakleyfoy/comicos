import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P81DiscoveryAlertRead } from "../api/client";
import { DiscoveryNav } from "../components/discovery/p81/DiscoveryNav";
import { StatusBanner } from "../components/StatusBanner";

export function DiscoveryAlertsPage(): JSX.Element {
  const [items, setItems] = useState<P81DiscoveryAlertRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listDiscoveryAlerts({ status: "ACTIVE", limit: 50 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load alerts.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const dismiss = async (id: number) => {
    await apiClient.updateDiscoveryAlert(id, { status: "DISMISSED" });
    await load();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-violet-300">P81-02</p>
          <h1 className="text-xl font-semibold">Discovery alerts</h1>
          <DiscoveryNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-3 px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {items.length === 0 ? (
          <p className="text-slate-500">No active alerts.</p>
        ) : (
          <ul className="space-y-3">
            {items.map((a) => (
              <li key={a.id} className="rounded-xl border border-slate-700 bg-slate-900/40 p-3">
                <p className="font-medium text-white">{a.title}</p>
                <p className="text-xs text-amber-200">
                  {a.priority} · {a.alert_type}
                </p>
                <p className="mt-1 text-sm text-slate-400">{a.message}</p>
                <button
                  type="button"
                  className="mt-2 text-xs text-slate-500 hover:text-slate-300"
                  onClick={() => void dismiss(a.id)}
                >
                  Dismiss
                </button>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
