import { useEffect, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type GradingPlatformCertificationRead,
  type GradingPlatformHealthRead,
  type GradingPlatformSummaryRead,
  type GradingPlatformValidationRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function statusTone(status: string): string {
  switch (status) {
    case "PASS":
    case "HEALTHY":
    case "APPROVED_FOR_PERSONAL_USE":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "FAIL":
    case "FAILED":
    case "NOT_READY":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    case "DISABLED":
      return "border-slate-500/30 bg-slate-500/10 text-slate-200";
    default:
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
  }
}

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

function StatusBadge({ value }: { value: string }): JSX.Element {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(value)}`}
    >
      {value}
    </span>
  );
}

export function GradingPlatformPage(): JSX.Element {
  const [summary, setSummary] = useState<GradingPlatformSummaryRead | null>(null);
  const [health, setHealth] = useState<GradingPlatformHealthRead | null>(null);
  const [validation, setValidation] = useState<GradingPlatformValidationRead | null>(null);
  const [certification, setCertification] = useState<GradingPlatformCertificationRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [summaryBody, healthBody, validationBody, certificationBody] = await Promise.all([
          apiClient.getGradingPlatformSummary(),
          apiClient.getGradingPlatformHealth(),
          apiClient.getGradingPlatformValidation(),
          apiClient.getGradingPlatformCertification(),
        ]);
        if (!cancelled) {
          setSummary(summaryBody);
          setHealth(healthBody);
          setValidation(validationBody);
          setCertification(certificationBody);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load grading platform.");
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

  const conditionCheck = validation?.checks.find((row) => row.check_code === "condition_intelligence");
  const predictionCheck = validation?.checks.find((row) => row.check_code === "grade_predictions");
  const recommendationCheck = validation?.checks.find((row) => row.check_code === "grading_recommendations");
  const calibrationCheck = validation?.checks.find((row) => row.check_code === "grading_validation");
  const reliabilityComponent = health?.components.find((row) => row.component_code === "validation_health");

  return (
    <AppShell>
      <PageHeader
        eyebrow="Grading Platform"
        title="Grading Platform"
        description="Closeout, validation, health, and certification for P49 Condition Intelligence through Grading Validation (P49-04)."
        actions={
          certification ? (
            <StatusBadge value={certification.platform_certified ? "Certified" : "Not certified"} />
          ) : undefined
        }
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading grading platform…</p> : null}

      {summary && health && validation && certification ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Overall Health" value={health.overall_status} />
            <StatCard label="Validation" value={validation.overall_status} />
            <StatCard label="Go-Live" value={certification.go_live_recommendation} />
            <StatCard label="Predictions" value={String(summary.prediction_summary.prediction_count)} />
          </div>

          <Panel title="Certification Status">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge value={certification.summary} />
              <StatusBadge value={certification.validation_status} />
              <StatusBadge value={certification.health_status} />
            </div>
            <ul className="mt-4 space-y-2 text-sm text-slate-300">
              {certification.certification_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Condition Intelligence Status">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm text-slate-300">
                  {summary.condition_summary.analysis_count} analyses · avg condition{" "}
                  {summary.condition_summary.average_condition_score.toFixed(1)}
                </p>
                {conditionCheck ? <StatusBadge value={conditionCheck.status} /> : null}
              </div>
            </Panel>

            <Panel title="Prediction Status">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm text-slate-300">
                  {summary.prediction_summary.prediction_count} predictions · avg confidence{" "}
                  {(summary.prediction_summary.average_confidence * 100).toFixed(0)}%
                </p>
                {predictionCheck ? <StatusBadge value={predictionCheck.status} /> : null}
              </div>
            </Panel>

            <Panel title="Recommendation Status">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm text-slate-300">
                  {summary.recommendation_summary.recommendation_count} recommendations · avg priority{" "}
                  {(summary.recommendation_summary.average_priority * 100).toFixed(0)}%
                </p>
                {recommendationCheck ? <StatusBadge value={recommendationCheck.status} /> : null}
              </div>
            </Panel>

            <Panel title="Calibration Status">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm text-slate-300">
                  {summary.calibration_summary.validation_count} validations · accuracy{" "}
                  {(summary.calibration_summary.average_accuracy_score * 100).toFixed(0)}%
                </p>
                {calibrationCheck ? <StatusBadge value={calibrationCheck.status} /> : null}
              </div>
            </Panel>

            <Panel title="Reliability Status">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm text-slate-300">
                  {summary.reliability_summary.reliability_metric_count} metrics ·{" "}
                  {summary.reliability_summary.drift_event_count} drift events
                </p>
                {reliabilityComponent ? <StatusBadge value={reliabilityComponent.health_status} /> : null}
              </div>
            </Panel>

            <Panel title="Top Grading Candidates">
              {!summary.top_grading_candidates.length ? (
                <p className="text-sm text-slate-500">No ranked candidates yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {summary.top_grading_candidates.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>{row.title}</span>
                      <span className="text-slate-400">{(row.priority_score * 100).toFixed(0)}%</span>
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
