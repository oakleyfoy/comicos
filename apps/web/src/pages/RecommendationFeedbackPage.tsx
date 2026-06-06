import { useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type P73RecommendationFeedbackDashboardRead,
  type P73RecommendationOutcomeDetailRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function RecommendationFeedbackPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<P73RecommendationFeedbackDashboardRead | null>(null);
  const [detail, setDetail] = useState<P73RecommendationOutcomeDetailRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getRecommendationFeedbackSummary();
        if (!cancelled) {
          setDashboard(body);
          const first = body.recent_outcomes[0];
          if (first) {
            setDetail(await apiClient.getRecommendationOutcomeDetail(first.id));
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load recommendation feedback.");
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

  const s = dashboard?.summary;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Recommendation feedback"
        title="Recommendation Outcomes"
        description="Track what happened after a recommendation — audit only (P73-01)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      {s ? (
        <div className="space-y-6">
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {[
              ["Created", s.recommendations_created],
              ["Viewed", s.viewed],
              ["Purchased", s.purchased],
              ["Graded", s.graded],
              ["Sold", s.sold],
            ].map(([label, val]) => (
              <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] uppercase text-slate-500">{label}</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{String(val)}</p>
              </div>
            ))}
          </div>
          <p className="text-sm text-slate-600">
            Attribution accuracy: {s.attribution_accuracy_pct.toFixed(0)}% ({s.attribution_matches}/
            {s.attribution_samples})
          </p>
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Recent outcomes</h2>
            <ul className="mt-3 space-y-2 text-sm">
              {dashboard.recent_outcomes.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    className="text-left text-indigo-600 hover:underline"
                    onClick={() => void apiClient.getRecommendationOutcomeDetail(row.id).then(setDetail)}
                  >
                    {row.series} #{row.issue} — {row.recommendation_type} → {row.current_status}
                  </button>
                </li>
              ))}
            </ul>
          </section>
          {detail ? (
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">Lifecycle timeline</h2>
              <ol className="mt-3 space-y-2 text-sm">
                {detail.timeline.map((step, idx) => (
                  <li key={`${step.event_type}-${idx}`}>
                    {step.event_type}{" "}
                    <span className="text-slate-500">({new Date(step.created_at).toLocaleString()})</span>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
        </div>
      ) : !loading ? (
        <p className="text-sm text-slate-500">No outcomes yet. Create one via the recommendation-feedback API.</p>
      ) : null}
    </AppShell>
  );
}
