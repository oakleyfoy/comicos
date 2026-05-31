import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type GradingValidationDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function GradingValidationPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<GradingValidationDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getGradingValidationDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load grading validation dashboard.");
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

  const accuracy = dashboard?.prediction_accuracy;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Grading observability"
        title="Grading Validation"
        description="Calibration, prediction accuracy, drift, reliability, and recommendation outcomes — validation only (P49-03)."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading grading validation…</p> : null}

      {dashboard && accuracy ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Validations" value={String(accuracy.validation_count)} />
            <StatCard label="Avg Variance" value={accuracy.average_variance.toFixed(2)} />
            <StatCard label="Accuracy Score" value={(accuracy.accuracy_score * 100).toFixed(0) + "%"} />
            <StatCard label="Drift Events" value={String(dashboard.drift_summary.event_count)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Prediction Accuracy">
              <p className="text-sm text-slate-300">
                {accuracy.validation_count
                  ? `${accuracy.validation_count} validation records; average variance ${accuracy.average_variance.toFixed(
                      2,
                    )}.`
                  : "Run validation with actual grades to populate accuracy metrics."}
              </p>
            </Panel>

            <Panel title="Calibration Metrics">
              {!dashboard.calibration_metrics.length ? (
                <p className="text-sm text-slate-500">No calibration metrics yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.calibration_metrics.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>
                        {row.grading_scale} · {row.total_predictions} preds
                      </span>
                      <span className="text-slate-400">{(row.accuracy_score * 100).toFixed(0)}%</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Drift Metrics">
              <p className="text-sm text-slate-300">
                {dashboard.drift_summary.latest_drift_type
                  ? `Latest: ${dashboard.drift_summary.latest_drift_type} (avg score ${dashboard.drift_summary.average_drift_score.toFixed(
                      2,
                    )})`
                  : "No drift events detected."}
              </p>
            </Panel>

            <Panel title="Reliability Metrics">
              {!dashboard.reliability_metrics.length ? (
                <p className="text-sm text-slate-500">No reliability metrics yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.reliability_metrics.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>{row.reliability_type}</span>
                      <span className="text-slate-400">{(row.metric_score * 100).toFixed(0)}%</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Recommendation Outcomes">
              {!dashboard.recommendation_outcomes.length ? (
                <p className="text-sm text-slate-500">No outcomes tracked yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.recommendation_outcomes.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>{row.outcome_type}</span>
                      <span className="text-slate-400">{(row.outcome_score * 100).toFixed(0)}%</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Agent Activity">
              {!dashboard.agent_activity.length ? (
                <p className="text-sm text-slate-500">No validation agent runs yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.agent_activity.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>{row.agent_code}</span>
                      <span className="text-slate-400">{row.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
