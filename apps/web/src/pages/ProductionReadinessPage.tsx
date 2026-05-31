import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type ProductionReadinessDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function statusTone(status: string): string {
  switch (status) {
    case "HEALTHY":
    case "PASS":
    case "CERTIFIED":
    case "GO":
    case "COMPLETE":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
    case "CONDITIONAL":
    case "NOT_RUN":
    case "PENDING":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "FAILED":
    case "FAIL":
    case "NOT_CERTIFIED":
    case "NO_GO":
    case "INCOMPLETE":
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

export function ProductionReadinessPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<ProductionReadinessDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getProductionReadinessDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load production readiness dashboard.");
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
        eyebrow="Certification"
        title="Production Readiness"
        description="P48 go-live certification for Oakley personal production use — validation, checklist, and assessment history."
        actions={
          dashboard ? (
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge value={dashboard.certification_status} />
              <StatusBadge value={dashboard.go_live_status} />
            </div>
          ) : null
        }
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-400">Loading production readiness…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Overall Readiness Score" value={dashboard.readiness_score.toFixed(1)} />
            <StatCard label="Certification Status" value={dashboard.certification_status} />
            <StatCard
              label="Checklist Status"
              value={`${dashboard.checklist_pass_count}/${dashboard.checklist_total} complete`}
            />
            <StatCard label="Go-Live Assessment" value={dashboard.go_live_status} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Platform Status">
              <ul className="space-y-3 text-sm text-slate-300">
                <li className="flex items-center justify-between gap-2">
                  <span>Marketplace</span>
                  <StatusBadge value={dashboard.marketplace_status} />
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span>Forecast</span>
                  <StatusBadge value={dashboard.forecast_status} />
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span>Data Protection</span>
                  <StatusBadge value={dashboard.data_protection_status} />
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span>Operations</span>
                  <StatusBadge value={dashboard.operations_status} />
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span>Agent Platform</span>
                  <StatusBadge value={dashboard.agent_platform_status} />
                </li>
              </ul>
            </Panel>

            <Panel title="Go-Live Assessment">
              {dashboard.latest_assessment ? (
                <div className="space-y-2 text-sm text-slate-400">
                  <p className="text-white">{dashboard.latest_assessment.assessment_summary}</p>
                  <p>Score {dashboard.latest_assessment.overall_score.toFixed(1)}</p>
                  <p className="text-xs text-slate-500">Assessed {new Date(dashboard.latest_assessment.assessed_at).toLocaleString()}</p>
                </div>
              ) : (
                <p className="text-sm text-slate-500">No go-live assessment recorded yet. Run certification from the API when ready.</p>
              )}
            </Panel>
          </div>

          {dashboard.latest_certification ? (
            <Panel title="Latest Certification">
              <p className="text-sm text-slate-400">{dashboard.latest_certification.certification_notes}</p>
              <p className="mt-2 text-xs text-slate-500">
                Certified {new Date(dashboard.latest_certification.certified_at).toLocaleString()}
              </p>
            </Panel>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}
