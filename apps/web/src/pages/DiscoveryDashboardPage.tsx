import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P81PersonalizedDiscoveryDashboardRead } from "../api/client";
import { DiscoveryPageLayout, PatriotPanel } from "../components/discovery/p81/DiscoveryPageLayout";

export function DiscoveryDashboardPage(): JSX.Element {
  const [dash, setDash] = useState<P81PersonalizedDiscoveryDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setDash(await apiClient.getDiscoveryDashboard({ refresh: true }));
    } catch (err) {
      setDash(null);
      setError(err instanceof ApiError ? err.message : "Failed to load discovery dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <DiscoveryPageLayout
      title="Discovery dashboard"
      error={error}
      onRetry={() => void load()}
      loading={loading && !dash}
    >
      {dash ? (
        <>
          <PatriotPanel title="Counts">
            <p>
              Must buy {dash.counts.must_buy ?? 0} · High {dash.counts.high_priority ?? 0} · Alerts{" "}
              {dash.counts.active_alerts ?? 0}
            </p>
          </PatriotPanel>
          <PatriotPanel title="Must buy">
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {dash.must_buy.map((o) => (
                <li key={o.opportunity.id}>
                  <Link to={`/discovery-opportunity/${o.opportunity.id}`} className="font-medium text-red-700 hover:underline">
                    {o.opportunity.title} ({o.personalized_score.toFixed(0)})
                  </Link>
                </li>
              ))}
            </ul>
          </PatriotPanel>
          <PatriotPanel title="Future pull list">
            <ul className="mt-2 space-y-1">
              {dash.future_pull_list.slice(0, 8).map((p) => (
                <li key={p.id}>
                  {p.title} — {p.recommendation_action} {p.recommendation_quantity || ""} · {p.pipeline_status}
                </li>
              ))}
            </ul>
          </PatriotPanel>
          <PatriotPanel title="Active alerts">
            <ul className="mt-2 space-y-1">
              {dash.active_alerts.map((a) => (
                <li key={a.id}>
                  [{a.priority}] {a.title}
                </li>
              ))}
            </ul>
          </PatriotPanel>
        </>
      ) : null}
    </DiscoveryPageLayout>
  );
}
