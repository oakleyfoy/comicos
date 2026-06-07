import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P81DiscoveryAlertRead } from "../api/client";
import { DiscoveryPageLayout, PatriotPanel } from "../components/discovery/p81/DiscoveryPageLayout";

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
    <DiscoveryPageLayout title="Discovery alerts" error={error} onRetry={() => void load()}>
      {items.length === 0 ? (
        <PatriotPanel>
          <p className="text-blue-800/80">No active alerts.</p>
        </PatriotPanel>
      ) : (
        <ul className="space-y-3">
          {items.map((a) => (
            <PatriotPanel key={a.id}>
              <p className="font-medium text-blue-950">{a.title}</p>
              <p className="text-xs font-medium text-red-700">
                {a.priority} · {a.alert_type}
              </p>
              <p className="mt-1 text-sm text-blue-900/80">{a.message}</p>
              <button type="button" className="mt-2 text-xs font-medium text-blue-800 hover:text-red-700" onClick={() => void dismiss(a.id)}>
                Dismiss
              </button>
            </PatriotPanel>
          ))}
        </ul>
      )}
    </DiscoveryPageLayout>
  );
}
