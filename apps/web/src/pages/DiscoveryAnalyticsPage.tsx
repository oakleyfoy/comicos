import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P81DiscoveryAnalyticsDashboardRead } from "../api/client";
import { DiscoveryPageLayout, PatriotPanel } from "../components/discovery/p81/DiscoveryPageLayout";

function Metric({ label, value }: { label: string; value: string | number }): JSX.Element {
  return (
    <div className="rounded-lg border border-blue-200 bg-white p-3 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-red-700">{label}</p>
      <p className="text-lg font-semibold text-blue-950">{value}</p>
    </div>
  );
}

export function DiscoveryAnalyticsPage(): JSX.Element {
  const [dash, setDash] = useState<P81DiscoveryAnalyticsDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setDash(await apiClient.getDiscoveryAnalyticsDashboard({ refresh: true }));
    } catch (err) {
      setDash(null);
      setError(err instanceof ApiError ? err.message : "Failed to load discovery analytics.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const act = dash?.activity;
  const pers = dash?.personalization_impact;

  return (
    <DiscoveryPageLayout
      title="Discovery analytics"
      eyebrow="P81-03 · Discovery"
      error={error}
      onRetry={() => void load()}
      loading={loading && !dash}
    >
      {dash && act && pers ? (
        <>
          <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Metric label="Discovered" value={act.opportunities_discovered} />
            <Metric label="Viewed" value={act.opportunities_viewed} />
            <Metric label="Saved" value={act.opportunities_saved} />
          </section>
          <PatriotPanel title="Opportunity performance">
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {dash.opportunity_performance.map((c) => (
                <li key={c.category}>
                  {c.category}: {c.detected} detected · {c.purchased} purchased · {c.conversion_rate_pct}%
                </li>
              ))}
            </ul>
          </PatriotPanel>
          <PatriotPanel title="Summary">
            <p>
              Alerts: {dash.alert_performance.alerts_sent} sent · {dash.alert_performance.alerts_opened} opened ·{" "}
              {dash.alert_performance.alerts_converted} converted
            </p>
            <p className="mt-2">
              Future pull: {dash.future_pull.recommendations} recs · {dash.future_pull.purchased} purchased ·{" "}
              {dash.future_pull.accuracy_pct}% accuracy
            </p>
            <p className="mt-2">Discovery portfolio ROI: {dash.discovery_roi.portfolio_roi_pct}%</p>
            <p className="mt-2">
              Personalization: {pers.opportunities_evaluated} evaluated · {pers.adjustment_rate_pct}% adjusted
            </p>
          </PatriotPanel>
        </>
      ) : null}
    </DiscoveryPageLayout>
  );
}
