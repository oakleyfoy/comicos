import { useEffect, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type RecommendationIntelligenceCertificationRead,
  type RecommendationIntelligenceHealthRead,
  type RecommendationIntelligenceSummaryRead,
  type RecommendationIntelligenceValidationRead,
  type RecommendationQualityCalibrationRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function statusTone(status: string): string {
  switch (status) {
    case "PASS":
    case "HEALTHY":
    case "APPROVED_FOR_RECOMMENDATION_USE":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
    case "APPROVED_WITH_WARNINGS":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "FAIL":
    case "FAILED":
    case "NOT_READY":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    default:
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
  }
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

export function RecommendationIntelligenceCertificationPage(): JSX.Element {
  const [validation, setValidation] = useState<RecommendationIntelligenceValidationRead | null>(null);
  const [health, setHealth] = useState<RecommendationIntelligenceHealthRead | null>(null);
  const [calibration, setCalibration] = useState<RecommendationQualityCalibrationRead | null>(null);
  const [summary, setSummary] = useState<RecommendationIntelligenceSummaryRead | null>(null);
  const [certification, setCertification] = useState<RecommendationIntelligenceCertificationRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [v, h, c, s, cert] = await Promise.all([
          apiClient.getRecommendationIntelligenceValidation(),
          apiClient.getRecommendationIntelligenceHealth(),
          apiClient.getRecommendationIntelligenceCalibration(),
          apiClient.getRecommendationIntelligenceSummary(),
          apiClient.getRecommendationIntelligenceCertification(),
        ]);
        if (!cancelled) {
          setValidation(v);
          setHealth(h);
          setCalibration(c);
          setSummary(s);
          setCertification(cert);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load recommendation intelligence certification.");
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
        eyebrow="Phase 51 closeout"
        title="Recommendation Intelligence Certification"
        description="Validation, health, calibration, and certification for P51 advisory recommendations (read-only)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading certification…</p> : null}

      {certification && summary ? (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge value={certification.go_live_recommendation} />
            <span className="text-sm text-slate-300">Readiness {certification.readiness_score.toFixed(0)}</span>
            <span className="text-sm text-slate-500">{certification.certification_version}</span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase text-slate-500">Must Buy</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.must_buy_count}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase text-slate-500">Strong Buy</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.strong_buy_count}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase text-slate-500">V2 total</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.total_recommendations_v2}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-[11px] uppercase text-slate-500">V1 preserved</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.v1_recommendation_count}</p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Certification">
              <ul className="space-y-2 text-sm text-slate-300">
                {certification.certification_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </Panel>
            <Panel title="V1 vs V2">
              <p className="text-sm text-slate-300">
                Moved up: {summary.v1_vs_v2_moved_up} · Moved down: {summary.v1_vs_v2_moved_down}
              </p>
              <p className="mt-2 text-sm text-slate-400">Explanations: {summary.explanation_count}</p>
            </Panel>
            {validation ? (
              <Panel title="Validation">
                <p className="mb-3">
                  <StatusBadge value={validation.overall_status} />
                </p>
                <ul className="space-y-2 text-sm text-slate-300">
                  {validation.checks.map((check) => (
                    <li key={check.check_code}>
                      {check.title}: {check.status} — {check.summary}
                    </li>
                  ))}
                </ul>
              </Panel>
            ) : null}
            {health ? (
              <Panel title="Health">
                <p className="mb-3">
                  <StatusBadge value={health.overall_status} />
                </p>
                <ul className="space-y-2 text-sm text-slate-300">
                  {health.components.map((c) => (
                    <li key={c.component_code}>
                      {c.title}: {c.health_status}
                    </li>
                  ))}
                </ul>
              </Panel>
            ) : null}
            {calibration ? (
              <Panel title="Calibration">
                <p className="mb-3">
                  <StatusBadge value={calibration.overall_status} />
                </p>
                <p className="text-sm text-slate-600">Score variance: {calibration.score_variance}</p>
                <ul className="mt-2 space-y-1 text-sm text-slate-300">
                  {calibration.findings.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </Panel>
            ) : null}
            <Panel title="Tier distribution">
              <ul className="text-sm text-slate-300">
                {calibration
                  ? Object.entries(calibration.tier_distribution).map(([tier, count]) => (
                      <li key={tier}>
                        {tier}: {count}
                      </li>
                    ))
                  : null}
              </ul>
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
