import { useEffect, useState, type ReactNode } from "react";

import {
  ApiError,
  apiClient,
  type ReleasePlatformCertificationRead,
  type ReleasePlatformHealthRead,
  type ReleasePlatformSummaryRead,
  type ReleasePlatformValidationRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function statusTone(status: string): string {
  switch (status) {
    case "PASS":
    case "HEALTHY":
    case "APPROVED_FOR_PRODUCTION":
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

function StatusBadge({ value }: { value: string }): JSX.Element {
  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${statusTone(value)}`}
    >
      {value}
    </span>
  );
}

export function ReleasePlatformCertificationPage(): JSX.Element {
  const [summary, setSummary] = useState<ReleasePlatformSummaryRead | null>(null);
  const [health, setHealth] = useState<ReleasePlatformHealthRead | null>(null);
  const [validation, setValidation] = useState<ReleasePlatformValidationRead | null>(null);
  const [certification, setCertification] = useState<ReleasePlatformCertificationRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [summaryBody, healthBody, validationBody, certificationBody] = await Promise.all([
          apiClient.getReleasePlatformSummary(),
          apiClient.getReleasePlatformHealth(),
          apiClient.getReleasePlatformValidation(),
          apiClient.getReleasePlatformCertification(),
        ]);
        if (!cancelled) {
          setSummary(summaryBody);
          setHealth(healthBody);
          setValidation(validationBody);
          setCertification(certificationBody);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load release platform certification.");
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
        eyebrow="Release Platform"
        title="Release Platform Certification"
        description="Closeout validation, health, and production certification for P50 Release Intelligence through Lunar variants (P50-05)."
        actions={
          certification ? (
            <StatusBadge value={certification.platform_certified ? "Certified" : "Not certified"} />
          ) : undefined
        }
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading release platform certification…</p> : null}

      {summary && health && validation && certification ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Platform Health" value={health.overall_status} />
            <StatCard label="Validation" value={validation.overall_status} />
            <StatCard label="Readiness Score" value={summary.platform_readiness_score.toFixed(1)} />
            <StatCard label="Go-Live" value={certification.go_live_recommendation} />
          </div>

          <Panel title="Certification Status">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge value={certification.summary} />
              <StatusBadge value={certification.validation_status} />
              <StatusBadge value={certification.health_status} />
              <span className="text-xs text-slate-400">
                {certification.certification_version} · {new Date(certification.certification_date).toLocaleString()}
              </span>
            </div>
            <ul className="mt-4 space-y-2 text-sm text-slate-300">
              {certification.certification_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Subsystem Validation">
              <ul className="space-y-3 text-sm text-slate-300">
                {validation.checks.map((check) => (
                  <li key={check.check_code} className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-white">{check.title}</p>
                      <p className="text-slate-400">{check.summary}</p>
                    </div>
                    <StatusBadge value={check.status} />
                  </li>
                ))}
              </ul>
            </Panel>

            <Panel title="Subsystem Health">
              <ul className="space-y-3 text-sm text-slate-300">
                {health.components.map((component) => (
                  <li key={component.component_code} className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-white">{component.title}</p>
                      <p className="text-slate-400">{component.summary}</p>
                    </div>
                    <StatusBadge value={component.health_status} />
                  </li>
                ))}
              </ul>
            </Panel>

            <Panel title="Release Statistics">
              <div className="grid gap-3 sm:grid-cols-2">
                <StatCard label="Releases" value={String(summary.total_releases)} />
                <StatCard label="Series" value={String(summary.total_series)} />
                <StatCard label="Variants" value={String(summary.total_variants)} />
                <StatCard label="New #1s" value={String(summary.total_new_number_ones)} />
                <StatCard label="Opportunities" value={String(summary.total_opportunities)} />
                <StatCard label="Watchlists" value={String(summary.total_watchlists)} />
                <StatCard label="FOC Alerts" value={String(summary.total_foc_alerts)} />
              </div>
            </Panel>

            <Panel title="Import & Scheduler">
              <div className="space-y-4 text-sm text-slate-300">
                <div>
                  <p className="font-medium text-white">Scheduler</p>
                  <p>
                    Enabled: {summary.scheduler.scheduler_enabled ? "Yes" : "No"}
                    {summary.scheduler.schedule_time_utc ? ` · UTC ${summary.scheduler.schedule_time_utc}` : ""}
                  </p>
                  {summary.scheduler.last_scheduled_run_status ? (
                    <p className="text-slate-400">
                      Last run: {summary.scheduler.last_scheduled_run_status}
                      {summary.scheduler.last_scheduled_run_at
                        ? ` · ${new Date(summary.scheduler.last_scheduled_run_at).toLocaleString()}`
                        : ""}
                    </p>
                  ) : null}
                </div>
                <div>
                  <p className="font-medium text-white">Imports</p>
                  <p>Total runs: {summary.import_summary.total_import_runs}</p>
                  <p className="text-slate-400">
                    Last status: {summary.import_summary.last_import_status ?? "—"} · processed{" "}
                    {summary.import_summary.last_import_records_processed}
                  </p>
                  {summary.import_summary.last_successful_import_at ? (
                    <p className="text-slate-400">
                      Last success: {new Date(summary.import_summary.last_successful_import_at).toLocaleString()}
                    </p>
                  ) : null}
                  {summary.import_summary.last_failed_import_at ? (
                    <p className="text-slate-400">
                      Last failure: {new Date(summary.import_summary.last_failed_import_at).toLocaleString()}
                    </p>
                  ) : null}
                </div>
              </div>
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
