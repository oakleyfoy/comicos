import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P84CollectorNotificationRead } from "../api/client";
import { PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";
import { patriotPrimaryButtonClass } from "../components/patriotTheme";

export function CollectorNotificationsPage(): JSX.Element {
  const [items, setItems] = useState<P84CollectorNotificationRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const body = await apiClient.listCollectorNotifications({ refresh: true, limit: 50 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load notifications.");
    } finally {
      setLoading(false);
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
    <PatriotPageLayout
      eyebrow="P84"
      title="Notifications"
      showExpansionNav
      error={error}
      onRetry={() => void load()}
      loading={loading && items.length === 0}
      maxWidthClass="max-w-4xl"
    >
      <div className="space-y-3">
        {items.map((n) => (
          <PatriotPanel key={n.id}>
            <p className="font-medium text-blue-950">
              [{n.priority}] {n.title}
            </p>
            <p className="text-blue-800">{n.message}</p>
            {n.status === "UNREAD" ? (
              <button type="button" className={`mt-2 ${patriotPrimaryButtonClass}`} onClick={() => void markRead(n.id)}>
                Mark read
              </button>
            ) : null}
          </PatriotPanel>
        ))}
      </div>
    </PatriotPageLayout>
  );
}
