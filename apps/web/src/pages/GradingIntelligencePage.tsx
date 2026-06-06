import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type GradingDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function GradingIntelligencePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<GradingDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getGradingIntelligenceDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load grading intelligence dashboard.");
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

  return (
    <AppShell>
      <PageHeader
        eyebrow="Grading advisory"
        title="Grading Intelligence"
        description="PSA/CGC-style grade predictions, recommendations, ROI, and submission priority — advisory only (P49-02)."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading grading intelligence…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Avg Confidence" value={(dashboard.average_confidence * 100).toFixed(0) + "%"} />
            <StatCard label="Avg ROI" value={dashboard.average_roi_percent.toFixed(1) + "%"} />
            <StatCard label="Predictions" value={String(dashboard.prediction_count)} />
            <StatCard label="Recommendations" value={String(dashboard.recommendation_count)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Grade Predictions">
              {!dashboard.prediction_summary.length ? (
                <p className="text-sm text-slate-500">No predictions yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.prediction_summary.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>
                        PSA {row.predicted_grade} ({row.grade_floor}–{row.grade_ceiling})
                      </span>
                      <span>{(row.confidence_score * 100).toFixed(0)}%</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Grading Recommendations">
              {!dashboard.recommendation_summary.length ? (
                <p className="text-sm text-slate-500">No recommendations yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.recommendation_summary.map((row) => (
                    <li key={row.id}>
                      <span className="font-medium text-slate-900">{row.recommendation_type}</span> — {row.title}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Top Submission Candidates">
              {!dashboard.top_grading_candidates.length ? (
                <p className="text-sm text-slate-500">Run priority ranking to populate candidates.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.top_grading_candidates.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>{row.title}</span>
                      <span>{row.priority_score.toFixed(2)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="ROI Analysis">
              {!dashboard.roi_summary.length ? (
                <p className="text-sm text-slate-500">No ROI analyses yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.roi_summary.map((row) => (
                    <li key={row.id}>
                      Raw ${row.raw_value.toFixed(0)} → Graded ${row.expected_graded_value.toFixed(0)} · ROI{" "}
                      {row.expected_roi_percent.toFixed(1)}%
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <Panel title="Agent Activity">
            {!dashboard.agent_activity.length ? (
              <p className="text-sm text-slate-500">No grading agent runs recorded.</p>
            ) : (
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.agent_activity.map((row) => (
                  <li key={row.id}>
                    {row.agent_code} · {row.status}
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <p className="text-xs text-slate-500">
            Review actions (accept / dismiss / reviewed) are available via the grading intelligence API. No automatic
            submissions or inventory changes are performed.
          </p>
        </div>
      ) : null}
    </AppShell>
  );
}
