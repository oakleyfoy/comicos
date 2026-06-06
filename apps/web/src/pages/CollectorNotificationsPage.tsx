import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P84CollectorNotificationRead } from "../api/client";
import { CollectorExpansionNav } from "../components/collector/CollectorExpansionNav";
import { StatusBanner } from "../components/StatusBanner";

export function CollectorNotificationsPage(): JSX.Element {
  const [items, setItems] = useState<P84CollectorNotificationRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listCollectorNotifications({ refresh: true, limit: 50 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load notifications.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function markRead(id: number) {
    await apiClient.updateCollectorNotification(id, { status: "READ" });
    void load();
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto max-w-4xl space-y-3">
          <p className="text-[11px] uppercase tracking-[0.2em] text-sky-300">P84</p>
          <h1 className="text-xl font-semibold">Notifications</h1>
          <CollectorExpansionNav />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-3 px-4 py-6 text-sm">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {items.map((n) => (
          <div key={n.id} className="rounded border border-slate-800 p-3">
            <p className="font-medium">
              [{n.priority}] {n.title}
            </p>
            <p className="text-slate-400">{n.message}</p>
            {n.status === "UNREAD" ? (
              <button type="button" className="mt-2 text-violet-300 hover:underline" onClick={() => void markRead(n.id)}>
                Mark read
              </button>
            ) : null}
          </div>
        ))}
      </main>
    </div>
  );
}
