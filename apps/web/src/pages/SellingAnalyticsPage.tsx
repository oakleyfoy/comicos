import { useCallback, useEffect, useState } from "react";

import { ApiError, apiClient, type P78SellingAnalyticsRead } from "../api/client";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { PatriotPanel } from "../components/PatriotPageLayout";
import { SellWorkflowPageLayout } from "../components/sell/p78/SellWorkflowPageLayout";

function MetricCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-lg border border-blue-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-red-700">{label}</p>
      <p className="mt-1 text-lg font-semibold text-blue-950">{value}</p>
    </div>
  );
}

export function SellingAnalyticsPage(): JSX.Element {
  const [analytics, setAnalytics] = useState<P78SellingAnalyticsRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      setAnalytics(await apiClient.getSellingAnalytics());
    } catch (err) {
      setAnalytics(null);
      setError(err instanceof ApiError ? err.message : "Failed to load selling analytics.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <SellWorkflowPageLayout
      title="Selling analytics"
      eyebrow="P78-02 · Sell"
      error={error}
      onRetry={() => void load()}
      loading={loading && !analytics}
    >
      {analytics ? (
        <>
          <NavPageLoadBanner status={analytics.status} message={analytics.message} />
          <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <MetricCard label="Revenue" value={`$${analytics.revenue.toFixed(0)}`} />
            <MetricCard label="Profit" value={`$${analytics.profit.toFixed(0)}`} />
            <MetricCard label="ROI" value={`${analytics.roi_pct.toFixed(0)}%`} />
            <MetricCard label="Listings created" value={String(analytics.listings_created)} />
            <MetricCard label="Listings sold" value={String(analytics.listings_sold)} />
            <MetricCard label="Sell conversion" value={`${analytics.sell_conversion_rate_pct.toFixed(1)}%`} />
          </section>
          <PatriotPanel title="Timing">
            <p>
              Average days to sell:{" "}
              {analytics.average_days_to_sell != null ? analytics.average_days_to_sell.toFixed(1) : "—"}
            </p>
            {analytics.sell_recommendation_accuracy_pct != null ? (
              <p className="mt-2">
                Sell recommendation accuracy: {analytics.sell_recommendation_accuracy_pct.toFixed(1)}%
              </p>
            ) : null}
          </PatriotPanel>
        </>
      ) : null}
    </SellWorkflowPageLayout>
  );
}
