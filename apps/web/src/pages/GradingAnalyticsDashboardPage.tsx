import { useEffect, useState } from "react";

import { ApiError, apiClient, type P72GradingAnalyticsDashboardRead, type P72GradingCertificationRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function GradingAnalyticsDashboardPage(): JSX.Element {
  const [analytics, setAnalytics] = useState<P72GradingAnalyticsDashboardRead | null>(null);
  const [cert, setCert] = useState<P72GradingCertificationRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [a, c] = await Promise.all([
          apiClient.getGradingAnalytics(),
          apiClient.getGradingCertification(),
        ]);
        if (!cancelled) {
          setAnalytics(a);
          setCert(c);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load grading analytics.");
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

  const p = analytics?.performance;
  const r = analytics?.roi;
  const port = analytics?.portfolio_impact;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Grading intelligence"
        title="Analytics & Certification"
        description="Was grading worth it? Performance, ROI, pressing, and production certification (P72-03)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading analytics…</p> : null}
      {cert ? (
        <div
          className={`mb-6 rounded-2xl border p-4 text-sm ${
            cert.approved_for_production
              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
              : "border-amber-200 bg-amber-50 text-amber-900"
          }`}
        >
          Platform status: <strong>{cert.platform_status}</strong>
        </div>
      ) : null}
      {analytics && p && r && port ? (
        <div className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase text-slate-500">Net ROI</p>
              <p className="mt-2 text-2xl font-semibold">{r.net_roi_pct.toFixed(1)}%</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase text-slate-500">Grading spend</p>
              <p className="mt-2 text-2xl font-semibold">${r.total_grading_spend.toFixed(0)}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase text-slate-500">Value added</p>
              <p className="mt-2 text-2xl font-semibold">${port.value_added_through_grading.toFixed(0)}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase text-slate-500">9.8 hit rate</p>
              <p className="mt-2 text-2xl font-semibold">{p.hit_rate_9_8_pct.toFixed(0)}%</p>
            </div>
          </section>
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Grade distribution</h2>
            <ul className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
              {Object.entries(p.grade_distribution_pct).map(([grade, pct]) => (
                <li key={grade}>
                  {grade}: {pct.toFixed(0)}%
                </li>
              ))}
            </ul>
          </section>
          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold">Top grading wins</h2>
              <ul className="mt-3 space-y-2 text-sm">
                {analytics.top_grading_wins.map((w) => (
                  <li key={w.title}>
                    {w.title} — ${w.actual_profit.toFixed(0)} ({w.actual_roi_pct.toFixed(0)}% ROI)
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold">Pressing</h2>
              <p className="mt-3 text-sm text-slate-600">
                Worth it? {analytics.pressing.pressing_worth_it ? "Yes" : "Unclear"} — success rate{" "}
                {analytics.pressing.pressing_success_rate_pct.toFixed(0)}%
              </p>
              <p className="mt-2 text-sm">
                ROI diff (pressed vs not): {analytics.pressing.roi_difference_pct.toFixed(1)}%
              </p>
            </div>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
