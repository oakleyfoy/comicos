import { useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type P74ReleaseCertificationRead,
  type P74ReleaseIntelligenceAnalyticsDashboardRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function ReleaseIntelligenceAnalyticsPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<P74ReleaseIntelligenceAnalyticsDashboardRead | null>(null);
  const [cert, setCert] = useState<P74ReleaseCertificationRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [dash, certification] = await Promise.all([
          apiClient.getReleaseIntelligenceAnalyticsDashboard(),
          apiClient.getReleaseMonitoringCertification(),
        ]);
        if (!cancelled) {
          setDashboard(dash);
          setCert(certification);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load release analytics.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const foc = dashboard?.foc_accuracy;
  const qty = dashboard?.quantity_accuracy;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Release intelligence"
        title="Release Analytics & Certification"
        description="Measure FOC and quantity recommendation performance (P74-03). Advisory analytics only."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      {dashboard && foc && qty ? (
        <div className="space-y-8">
          <section className="grid gap-3 sm:grid-cols-4">
            {[
              ["Upcoming", dashboard.upcoming_count],
              ["Past tracked", dashboard.past_performance_count],
              ["Platform confidence", `${dashboard.platform_confidence_pct}%`],
              ["Certification", cert?.platform_status ?? dashboard.certification_status],
            ].map(([label, value]) => (
              <div key={String(label)} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="text-2xl font-semibold text-slate-900">{value}</p>
              </div>
            ))}
          </section>

          <section className="grid gap-6 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">FOC accuracy</h2>
              <ul className="mt-2 space-y-1 text-sm text-slate-700">
                <li>Accuracy: {foc.accuracy_rate_pct}%</li>
                <li>Upgrade accuracy: {foc.upgrade_accuracy_pct}%</li>
                <li>Downgrade accuracy: {foc.downgrade_accuracy_pct}%</li>
                <li>Missed opportunity: {foc.missed_opportunity_rate_pct}%</li>
              </ul>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">Quantity accuracy</h2>
              <ul className="mt-2 space-y-1 text-sm text-slate-700">
                <li>Success: {qty.success_rate_pct}%</li>
                <li>Failure: {qty.failure_rate_pct}%</li>
                <li>Avg ROI: {qty.average_roi_pct}%</li>
                <li>Median ROI: {qty.median_roi_pct}%</li>
              </ul>
            </div>
          </section>

          <section className="grid gap-6 md:grid-cols-2">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Best categories</h2>
              <ul className="mt-2 space-y-1 text-sm text-slate-700">
                {dashboard.best_categories.map((c) => (
                  <li key={c.category_key}>
                    {c.category_key}: {c.success_rate_pct}% success ({c.sample_count} samples)
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Worst categories</h2>
              <ul className="mt-2 space-y-1 text-sm text-slate-700">
                {dashboard.worst_categories.map((c) => (
                  <li key={c.category_key}>
                    {c.category_key}: {c.success_rate_pct}% success ({c.sample_count} samples)
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Recent outcomes</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {dashboard.recent_outcomes.slice(0, 12).map((o) => (
                <li key={o.id}>
                  Issue {o.release_issue_id}: rec {o.recommended_quantity} / bought {o.actual_quantity_purchased} —{" "}
                  {o.outcome_status} ({o.purchase_action})
                </li>
              ))}
            </ul>
          </section>

          {cert ? (
            <section>
              <h2 className="text-sm font-semibold text-slate-900">Certification checks</h2>
              <ul className="mt-2 space-y-1 text-sm text-slate-700">
                {cert.checks.map((c) => (
                  <li key={c.component}>
                    {c.component}: {c.passed ? "pass" : "fail"} — {c.detail}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}
