import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P83CollectionValuationDashboardRead } from "../api/client";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { PatriotInlineLink, PatriotPageLayout, PatriotPanel } from "../components/PatriotPageLayout";

export function CollectionValuationDashboardPage(): JSX.Element {
  const [dash, setDash] = useState<P83CollectionValuationDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setDash(await apiClient.getCollectionValuationDashboard());
    } catch (err) {
      setDash(null);
      setError(err instanceof ApiError ? err.message : "Failed to load valuation dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <PatriotPageLayout
      eyebrow="P83 · Collection valuation"
      title="Collection valuation dashboard"
      showExpansionNav
      error={error}
      onRetry={() => void load()}
      loading={loading && !dash}
      headerExtra={
        <>
          <PatriotInlineLink to="/collection-forecast">Forecast</PatriotInlineLink>
          {" · "}
          <PatriotInlineLink to="/collection-risk">Risk</PatriotInlineLink>
          {" · "}
          <PatriotInlineLink to="/collection-scenarios">Scenarios</PatriotInlineLink>
          {" · "}
          <PatriotInlineLink to="/collection-optimization">Optimization</PatriotInlineLink>
        </>
      }
    >
      {dash ? (
        <>
          <NavPageLoadBanner status={dash.status} message={dash.message} />
          <PatriotPanel title="Snapshot">
            <p>
              Current value ${dash.forecast.current_value.toFixed(2)} · Risk {dash.risk.risk_category} (
              {dash.risk.risk_score.toFixed(0)})
            </p>
          </PatriotPanel>
          <PatriotPanel title="Buy targets">
            <ul className="list-disc pl-5">
              {dash.optimization.buy_targets.length === 0 ? (
                <li className="text-blue-800/80">None yet.</li>
              ) : (
                dash.optimization.buy_targets.map((b, i) => <li key={i}>{String(b.title ?? "—")}</li>)
              )}
            </ul>
          </PatriotPanel>
        </>
      ) : null}
    </PatriotPageLayout>
  );
}
