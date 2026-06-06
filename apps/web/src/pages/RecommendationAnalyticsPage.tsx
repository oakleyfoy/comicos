import { useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type P73RecommendationCertificationRead,
  type P73RecommendationQualityDashboardRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function RecommendationAnalyticsPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<P73RecommendationQualityDashboardRead | null>(null);
  const [cert, setCert] = useState<P73RecommendationCertificationRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [body, certification] = await Promise.all([
          apiClient.getRecommendationQualityDashboard(),
          apiClient.getRecommendationFeedbackCertification(),
        ]);
        if (!cancelled) {
          setDashboard(body);
          setCert(certification);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load recommendation analytics.");
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

  const conf = dashboard?.confidence;
  const eff = dashboard?.effectiveness;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Recommendation feedback"
        title="Recommendation Quality Dashboard"
        description="Observe, measure, and calibrate from outcome history (P73-02 + P73-03)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {cert?.approved_for_production ? (
        <StatusBanner tone="success">Platform status: {cert.platform_status}</StatusBanner>
      ) : null}
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      {dashboard && conf && eff ? (
        <div className="space-y-8">
          <section>
            <h2 className="text-sm font-semibold text-slate-900">Performance summary</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] uppercase text-slate-500">Overall accuracy</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">
                  {dashboard.overall_accuracy_pct.toFixed(0)}%
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] uppercase text-slate-500">Overall ROI</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">
                  {dashboard.overall_roi_pct.toFixed(0)}%
                </p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Recommendation confidence</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-4">
              {(
                [
                  ["BUY", conf.buy_confidence],
                  ["GRADE", conf.grade_confidence],
                  ["SELL", conf.sell_confidence],
                  ["WATCH", conf.watch_confidence],
                ] as const
              ).map(([label, score]) => (
                <div key={label} className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
                  <p className="text-xs text-slate-600">{label}</p>
                  <p className="text-2xl font-semibold text-indigo-900">{score}</p>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Category performance</h2>
            <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-slate-100 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2">Type</th>
                    <th className="px-4 py-2">Count</th>
                    <th className="px-4 py-2">Success</th>
                    <th className="px-4 py-2">Avg ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.category_performance.map((row) => (
                    <tr key={row.recommendation_type} className="border-b border-slate-50">
                      <td className="px-4 py-2 font-medium">{row.recommendation_type}</td>
                      <td className="px-4 py-2">{row.recommendation_count}</td>
                      <td className="px-4 py-2">{row.success_rate_pct.toFixed(0)}%</td>
                      <td className="px-4 py-2">{row.average_roi_pct.toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Best types: {dashboard.best_recommendation_types.join(", ") || "—"} · Worst:{" "}
              {dashboard.worst_recommendation_types.join(", ") || "—"}
            </p>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">ROI & effectiveness</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-xs text-slate-600">Expected ROI</p>
                <p className="text-xl font-semibold">{eff.expected_roi_pct.toFixed(0)}%</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-xs text-slate-600">Actual ROI</p>
                <p className="text-xl font-semibold">{eff.actual_roi_pct.toFixed(0)}%</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-xs text-slate-600">Win rate</p>
                <p className="text-xl font-semibold">{eff.win_rate_pct.toFixed(0)}%</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <p className="text-xs text-slate-600">Loss rate</p>
                <p className="text-xl font-semibold">{eff.loss_rate_pct.toFixed(0)}%</p>
              </div>
            </div>
            <ul className="mt-3 space-y-1 text-sm text-slate-700">
              {eff.by_type.map((t) => (
                <li key={t.recommendation_type}>
                  {t.recommendation_type}: expected {t.expected_roi_pct}% / actual {t.actual_roi_pct}% —{" "}
                  {t.accuracy_label}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Category calibration</h2>
            <div className="mt-3 overflow-x-auto rounded-2xl border border-slate-200 bg-white">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-slate-100 bg-slate-50 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2">Category</th>
                    <th className="px-4 py-2">Count</th>
                    <th className="px-4 py-2">Success</th>
                    <th className="px-4 py-2">Avg / Median ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.category_calibration.map((row) => (
                    <tr key={row.calibration_category} className="border-b border-slate-50">
                      <td className="px-4 py-2">{row.calibration_category}</td>
                      <td className="px-4 py-2">{row.recommendation_count}</td>
                      <td className="px-4 py-2">{row.success_rate_pct.toFixed(0)}%</td>
                      <td className="px-4 py-2">
                        {row.average_roi_pct.toFixed(0)}% / {row.median_roi_pct.toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
