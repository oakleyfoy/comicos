import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P81PersonalizedOpportunityRead } from "../api/client";
import { DiscoveryPageLayout, PatriotPanel } from "../components/discovery/p81/DiscoveryPageLayout";

export function DiscoveryOpportunitiesPage(): JSX.Element {
  const [items, setItems] = useState<P81PersonalizedOpportunityRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const body = await apiClient.listPersonalizedDiscovery({ refresh: true, limit: 50 });
      setItems(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load opportunities.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <DiscoveryPageLayout title="Discovery opportunities" error={error} onRetry={() => void load()}>
      {items.length === 0 ? (
        <PatriotPanel>
          <p className="text-blue-800/80">No personalized opportunities yet.</p>
        </PatriotPanel>
      ) : (
        <ul className="space-y-3">
          {items.map((o) => (
            <PatriotPanel key={o.opportunity.id}>
              <Link to={`/discovery-opportunity/${o.opportunity.id}`} className="font-medium text-red-700 hover:underline">
                {o.opportunity.title}
              </Link>
              <p className="text-xs text-blue-800/70">
                {o.priority_category} · Global {o.discovery_score.toFixed(0)} → Personalized {o.personalized_score.toFixed(0)}
              </p>
              <p className="mt-1 text-sm font-medium text-blue-950">
                {o.recommendation_action}
                {o.recommendation_quantity > 0 ? ` × ${o.recommendation_quantity}` : ""}
              </p>
            </PatriotPanel>
          ))}
        </ul>
      )}
    </DiscoveryPageLayout>
  );
}
