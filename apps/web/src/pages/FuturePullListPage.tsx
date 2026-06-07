import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P81FuturePullListItemRead } from "../api/client";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { DiscoveryPageLayout, PatriotPanel } from "../components/discovery/p81/DiscoveryPageLayout";

export function FuturePullListPage(): JSX.Element {
  const [items, setItems] = useState<P81FuturePullListItemRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loadStatus, setLoadStatus] = useState<string | undefined>();
  const [loadMessage, setLoadMessage] = useState<string | undefined>();

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.getFuturePullList({ refresh: false, limit: 50 });
      setItems(body.items);
      setLoadStatus(body.status);
      setLoadMessage(body.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load future pull list.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <DiscoveryPageLayout title="Future pull list" error={error} onRetry={() => void load()}>
      <NavPageLoadBanner status={loadStatus} message={loadMessage} />
      {items.length === 0 ? (
        <PatriotPanel>
          <p className="text-blue-800/80">No future opportunities yet.</p>
        </PatriotPanel>
      ) : (
        <ul className="space-y-3">
          {items.map((p) => (
            <PatriotPanel key={p.id}>
              <p className="font-medium text-blue-950">{p.title}</p>
              <p className="text-xs text-blue-800/70">
                {p.pipeline_status} · {p.watch_level} watch · Score {p.personalized_score.toFixed(0)}
              </p>
              <p className="mt-1 text-sm text-blue-900">
                {p.recommendation_action}
                {p.recommendation_quantity > 0 ? ` × ${p.recommendation_quantity}` : ""}
              </p>
            </PatriotPanel>
          ))}
        </ul>
      )}
    </DiscoveryPageLayout>
  );
}
