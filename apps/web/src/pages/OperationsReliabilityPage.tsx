import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type OperationsReliabilityDashboardRead,
  type PlatformHealthCheckRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function statusTone(status: string): string {
  switch (status) {
    case "HEALTHY":
    case "PASS":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "FAILED":
    case "FAIL":
      return "border-rose-400/30 bg-rose-400/10 text-rose-100";
    default:
      return "border-cyan-400/30 bg-cyan-400/10 text-cyan-100";
  }
}

function StatusBadge({ value }: { value: string }): JSX.Element {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(value)}`}>
      {value}
    </span>
  );
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

function hasRecordedRunAt(at: string | null | undefined): boolean {
  return at != null && at !== "";
}

function CertificationStats({
  lastAt,
  readinessScore,
  certificationResult,
  validationStatusLabel,
  validationStatus,
}: {
  lastAt: string;
  readinessScore: number;
  certificationResult: string;
  validationStatusLabel: string;
  validationStatus: string;
}): JSX.Element {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <StatCard label="Last Certification" value={lastAt.slice(0, 19).replace("T", " ")} />
      <StatCard label="Readiness Score" value={readinessScore.toFixed(1)} />
      <StatCard label="Certification Result" value={certificationResult} />
      <StatCard label={validationStatusLabel} value={validationStatus} />
    </div>
  );
}

function HealthList({ rows }: { rows: PlatformHealthCheckRead[] }): JSX.Element {
  if (!rows.length) return <p className="text-sm text-slate-500">No subsystem health checks recorded yet.</p>;
  return (
    <ul className="space-y-3">
      {rows.map((row) => (
        <li key={row.check_uuid} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-white">{row.subsystem}</p>
            <StatusBadge value={row.health_status} />
          </div>
          <p className="mt-2 text-sm text-slate-400">Score {row.health_score.toFixed(0)}</p>
        </li>
      ))}
    </ul>
  );
}

export function OperationsReliabilityPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<OperationsReliabilityDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getOperationsReliabilityHealth();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load operations reliability dashboard.");
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

  const openIssues = useMemo(() => dashboard?.issues.filter((issue) => issue.issue_status === "OPEN") ?? [], [dashboard?.issues]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Operations"
        title="Operations Reliability"
        description="Platform health, job and queue monitoring, reliability issues, and recovery recommendations."
        actions={
          dashboard ? (
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge value={dashboard.summary.platform_health_status} />
              <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-100">
                Readiness {dashboard.summary.readiness_score.toFixed(0)}
              </span>
            </div>
          ) : null
        }
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading operations command center…</p> : null}

      {!loading && dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Overall Readiness Score" value={dashboard.summary.readiness_score.toFixed(0)} />
            <StatCard label="Platform Health" value={dashboard.summary.platform_health_status} />
            <StatCard label="Open Issues" value={String(dashboard.summary.open_issue_count)} />
            <StatCard label="Recommendations" value={String(dashboard.summary.recommendation_count)} />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Platform Health">
              <StatCard label="Subsystem Health" value={String(dashboard.health_checks.length)} />
            </Panel>
            <Panel title="Subsystem Health">
              <HealthList rows={dashboard.health_checks} />
            </Panel>
            <Panel title="Reliability Issues">
              {openIssues.length ? (
                <ul className="space-y-3">
                  {openIssues.map((issue) => (
                    <li key={issue.issue_uuid} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm font-medium text-white">{issue.issue_type}</p>
                        <StatusBadge value={issue.severity} />
                      </div>
                      <p className="mt-2 text-sm text-slate-400">{issue.subsystem}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No open reliability issues.</p>
              )}
            </Panel>
            <Panel title="Job Metrics">
              {dashboard.job_metrics.length ? (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.job_metrics.map((metric) => (
                    <li key={metric.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-3">
                      {metric.job_type}: {metric.total_jobs} total, {metric.failed_jobs} failed
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No job metrics captured yet.</p>
              )}
            </Panel>
            <Panel title="Queue Metrics">
              {dashboard.queue_metrics.length ? (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.queue_metrics.map((metric) => (
                    <li key={metric.id} className="rounded-2xl border border-white/10 bg-slate-950/40 p-3">
                      {metric.queue_name}: {metric.queued_count} queued, {metric.failed_count} failed
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No queue metrics captured yet.</p>
              )}
            </Panel>
            <Panel title="Recovery Recommendations">
              {dashboard.recommendations.length ? (
                <ul className="space-y-3">
                  {dashboard.recommendations.map((rec) => (
                    <li key={rec.recommendation_uuid} className="rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                      <p className="text-sm font-medium text-white">{rec.title}</p>
                      <p className="mt-2 text-sm text-slate-400">{rec.description.replace(/^\[owner:\d+\]\s*/, "")}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No recovery recommendations yet.</p>
              )}
            </Panel>
            <Panel title="Pull List Automation">
              {dashboard.pull_list_automation ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <StatCard
                    label="Last Run"
                    value={
                      dashboard.pull_list_automation.last_run
                        ? dashboard.pull_list_automation.last_run.slice(0, 19).replace("T", " ")
                        : "—"
                    }
                  />
                  <StatCard label="Status" value={dashboard.pull_list_automation.status} />
                  <StatCard label="Runtime (ms)" value={String(dashboard.pull_list_automation.runtime_ms)} />
                  <StatCard label="Decisions Generated" value={String(dashboard.pull_list_automation.decisions_generated)} />
                  <StatCard label="Actions Generated" value={String(dashboard.pull_list_automation.actions_generated)} />
                </div>
              ) : (
                <p className="text-sm text-slate-500">No pull list automation runs recorded yet.</p>
              )}
            </Panel>
            <Panel title="Pull List Certification">
              {hasRecordedRunAt(dashboard.pull_list_certification?.last_certification_at) ? (
                <CertificationStats
                  lastAt={dashboard.pull_list_certification!.last_certification_at!}
                  readinessScore={dashboard.pull_list_certification!.readiness_score}
                  certificationResult={dashboard.pull_list_certification!.certification_result}
                  validationStatusLabel="Validation Status"
                  validationStatus={dashboard.pull_list_certification!.validation_status}
                />
              ) : (
                <p className="text-sm text-slate-500">No pull list certification runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="Portfolio Intelligence Certification">
              {hasRecordedRunAt(dashboard.portfolio_certification?.last_certification_at) ? (
                <CertificationStats
                  lastAt={dashboard.portfolio_certification!.last_certification_at!}
                  readinessScore={dashboard.portfolio_certification!.readiness_score}
                  certificationResult={dashboard.portfolio_certification!.certification_result}
                  validationStatusLabel="Validation Status"
                  validationStatus={dashboard.portfolio_certification!.validation_status}
                />
              ) : (
                <p className="text-sm text-slate-500">No portfolio certification runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="Acquisition Intelligence Certification">
              {hasRecordedRunAt(dashboard.acquisition_certification?.last_certification_at) ? (
                <CertificationStats
                  lastAt={dashboard.acquisition_certification!.last_certification_at!}
                  readinessScore={dashboard.acquisition_certification!.readiness_score}
                  certificationResult={dashboard.acquisition_certification!.certification_result}
                  validationStatusLabel="Validation Status"
                  validationStatus={dashboard.acquisition_certification!.validation_status}
                />
              ) : (
                <p className="text-sm text-slate-500">No acquisition certification runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="Future Release Intelligence Certification">
              {hasRecordedRunAt(dashboard.future_release_certification?.last_certification_at) ? (
                <CertificationStats
                  lastAt={dashboard.future_release_certification!.last_certification_at!}
                  readinessScore={dashboard.future_release_certification!.readiness_score}
                  certificationResult={dashboard.future_release_certification!.certification_result}
                  validationStatusLabel="Validation Status"
                  validationStatus={dashboard.future_release_certification!.validation_status}
                />
              ) : (
                <p className="text-sm text-slate-500">No future release certification runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="Industry Scanner Automation">
              {hasRecordedRunAt(dashboard.industry_scanner_automation?.last_run ?? null) ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <StatCard
                    label="Last Run"
                    value={dashboard.industry_scanner_automation!.last_run!.slice(0, 19).replace("T", " ")}
                  />
                  <StatCard label="Status" value={dashboard.industry_scanner_automation!.status} />
                  <StatCard label="Trigger" value={dashboard.industry_scanner_automation!.trigger_type ?? "—"} />
                  <StatCard label="Runtime (ms)" value={String(dashboard.industry_scanner_automation!.runtime_ms)} />
                  <StatCard label="Releases Scanned" value={String(dashboard.industry_scanner_automation!.releases_scanned)} />
                  <StatCard
                    label="Candidates Created"
                    value={String(dashboard.industry_scanner_automation!.candidates_created)}
                  />
                  <StatCard label="Signals Upserted" value={String(dashboard.industry_scanner_automation!.signals_upserted)} />
                  <StatCard label="Scores Updated" value={String(dashboard.industry_scanner_automation!.scores_updated)} />
                  {dashboard.industry_scanner_automation!.scan_skipped ? (
                    <p className="sm:col-span-2 text-xs text-slate-400">Latest refresh reused prior scan (catalog unchanged).</p>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-slate-500">No industry scanner automation runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="Spec Pipeline Automation">
              {hasRecordedRunAt(dashboard.spec_automation?.last_run ?? null) ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <StatCard
                    label="Last Run"
                    value={dashboard.spec_automation!.last_run!.slice(0, 19).replace("T", " ")}
                  />
                  <StatCard label="Status" value={dashboard.spec_automation!.status} />
                  <StatCard label="Runtime (ms)" value={String(dashboard.spec_automation!.runtime_ms)} />
                  <StatCard label="Inputs Processed" value={String(dashboard.spec_automation!.inputs_processed)} />
                  <StatCard
                    label="Baseline Scores"
                    value={String(dashboard.spec_automation!.baseline_scores_created)}
                  />
                  <StatCard label="AI Evaluations" value={String(dashboard.spec_automation!.ai_evaluations_created)} />
                  <StatCard label="Top Picks Created" value={String(dashboard.spec_automation!.top_picks_created)} />
                </div>
              ) : (
                <p className="text-sm text-slate-500">No spec automation runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="AI Spec Engine Certification">
              {hasRecordedRunAt(dashboard.ai_spec_certification?.last_certification_at ?? null) ? (
                <CertificationStats
                  lastAt={dashboard.ai_spec_certification!.last_certification_at!}
                  readinessScore={dashboard.ai_spec_certification!.readiness_score}
                  certificationResult={dashboard.ai_spec_certification!.certification_result}
                  validationStatusLabel="Validation Status"
                  validationStatus={dashboard.ai_spec_certification!.validation_status}
                />
              ) : (
                <p className="text-sm text-slate-500">No AI spec certification runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="Industry Scanner Certification">
              {hasRecordedRunAt(dashboard.industry_scanner_certification?.last_certification_at ?? null) ? (
                <CertificationStats
                  lastAt={dashboard.industry_scanner_certification!.last_certification_at!}
                  readinessScore={dashboard.industry_scanner_certification!.readiness_score}
                  certificationResult={dashboard.industry_scanner_certification!.certification_result}
                  validationStatusLabel="Validation Status"
                  validationStatus={dashboard.industry_scanner_certification!.validation_status}
                />
              ) : (
                <p className="text-sm text-slate-500">No industry scanner certification runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="Exit Intelligence Certification">
              {hasRecordedRunAt(dashboard.exit_certification?.last_certification_at) ? (
                <CertificationStats
                  lastAt={dashboard.exit_certification!.last_certification_at!}
                  readinessScore={dashboard.exit_certification!.readiness_score}
                  certificationResult={dashboard.exit_certification!.certification_result}
                  validationStatusLabel="Validation Status"
                  validationStatus={dashboard.exit_certification!.validation_status}
                />
              ) : (
                <p className="text-sm text-slate-500">No exit certification runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="Final Platform Certification">
              {hasRecordedRunAt(dashboard.final_platform_certification?.last_certification_at) ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <StatCard
                    label="Last Certification"
                    value={dashboard.final_platform_certification!.last_certification_at!.slice(0, 19).replace("T", " ")}
                  />
                  <StatCard
                    label="Readiness Score"
                    value={dashboard.final_platform_certification!.readiness_score.toFixed(1)}
                  />
                  <StatCard label="Certification Result" value={dashboard.final_platform_certification!.certification_result} />
                  <StatCard label="Health Status" value={dashboard.final_platform_certification!.health_status} />
                  {dashboard.final_platform_certification!.validation_summary ? (
                    <p className="sm:col-span-2 text-xs text-slate-400">
                      {dashboard.final_platform_certification!.validation_summary}
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-slate-500">No final platform certification runs recorded for this owner.</p>
              )}
            </Panel>
            <Panel title="Production Readiness">
              {hasRecordedRunAt(dashboard.production_readiness?.last_run_at) ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  <StatCard
                    label="Last Run"
                    value={dashboard.production_readiness!.last_run_at!.slice(0, 19).replace("T", " ")}
                  />
                  <StatCard label="Readiness Score" value={dashboard.production_readiness!.readiness_score.toFixed(1)} />
                  <StatCard label="Go-Live Result" value={dashboard.production_readiness!.go_live_result} />
                  <StatCard label="Health Status" value={dashboard.production_readiness!.health_status} />
                  {dashboard.production_readiness!.recommendations ? (
                    <p className="sm:col-span-2 text-xs text-slate-400">{dashboard.production_readiness!.recommendations}</p>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-slate-500">No production readiness runs recorded for this owner.</p>
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
