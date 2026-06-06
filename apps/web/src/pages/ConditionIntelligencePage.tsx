import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type ConditionDashboardRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function statusTone(status: string): string {
  switch (status) {
    case "PASS":
    case "COMPLETED":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "WARNING":
    case "RUNNING":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "FAIL":
    case "FAILED":
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

export function ConditionIntelligencePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<ConditionDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const body = await apiClient.getConditionIntelligenceDashboard();
        if (!cancelled) setDashboard(body);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Unable to load condition intelligence dashboard.");
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
        eyebrow="Scan analysis"
        title="Condition Intelligence"
        description="Scan quality, defect detection, condition profiling, and subgrades — foundation for future grading decisions (P49-01)."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading condition intelligence…</p> : null}

      {dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Condition Scores" value={dashboard.average_condition_score.toFixed(1)} />
            <StatCard label="Scan Quality" value={dashboard.average_quality_score.toFixed(1)} />
            <StatCard label="Analyses" value={String(dashboard.analysis_count)} />
            <StatCard label="Agent Runs" value={String(dashboard.execution_count)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Condition Profiles">
              {!dashboard.condition_summary.length ? (
                <p className="text-sm text-slate-500">No condition profiles yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.condition_summary.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>Analysis #{row.analysis_id}</span>
                      <span>
                        {row.overall_condition_score.toFixed(1)} ({(row.confidence_score * 100).toFixed(0)}% conf.)
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Scan Quality">
              {!dashboard.scan_quality_summary.length ? (
                <p className="text-sm text-slate-500">No quality assessments yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.scan_quality_summary.map((row) => (
                    <li key={row.id} className="flex items-center justify-between gap-2">
                      <span>Analysis #{row.analysis_id}</span>
                      <StatusBadge value={row.quality_status} />
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Detected Defects">
              {!dashboard.defect_summary.length ? (
                <p className="text-sm text-slate-500">No defects recorded.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.defect_summary.map((row) => (
                    <li key={row.id}>
                      {row.defect_type} · {row.defect_location} · {row.defect_severity}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Subgrades">
              {!dashboard.subgrade_summary.length ? (
                <p className="text-sm text-slate-500">No subgrades generated.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.subgrade_summary.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>{row.subgrade_type}</span>
                      <span>{row.score.toFixed(1)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <Panel title="Agent Activity">
            {!dashboard.agent_activity.length ? (
              <p className="text-sm text-slate-500">No agent executions yet.</p>
            ) : (
              <ul className="space-y-2 text-sm text-slate-300">
                {dashboard.agent_activity.map((row) => (
                  <li key={row.id} className="flex flex-wrap items-center justify-between gap-2">
                    <span>{row.agent_code}</span>
                    <StatusBadge value={row.status} />
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      ) : null}
    </AppShell>
  );
}
