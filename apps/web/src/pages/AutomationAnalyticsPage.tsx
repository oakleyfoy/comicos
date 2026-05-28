import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AutomationAnalyticsComparisonRead,
  type AutomationAnalyticsIssueRead,
  type AutomationAnalyticsMetricRead,
  type AutomationAnalyticsSnapshotRead,
  type AutomationAnalyticsTrendRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function Panel({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/65 p-5">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
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

export function AutomationAnalyticsPage() {
  const [snapshots, setSnapshots] = useState<AutomationAnalyticsSnapshotRead[]>([]);
  const [metrics, setMetrics] = useState<AutomationAnalyticsMetricRead[]>([]);
  const [trends, setTrends] = useState<AutomationAnalyticsTrendRead[]>([]);
  const [comparisons, setComparisons] = useState<AutomationAnalyticsComparisonRead[]>([]);
  const [issues, setIssues] = useState<AutomationAnalyticsIssueRead[]>([]);
  const [selected, setSelected] = useState<AutomationAnalyticsSnapshotRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void refresh();
  }, []);

  async function refresh(snapshotId?: number | null): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [snapshotResponse, issueResponse] = await Promise.all([
        apiClient.listAutomationAnalyticsSnapshots({ limit: 50, offset: 0 }),
        apiClient.listAutomationAnalyticsIssues({ limit: 50, offset: 0 }),
      ]);
      const nextSnapshots = snapshotResponse.items as AutomationAnalyticsSnapshotRead[];
      setSnapshots(nextSnapshots);
      setIssues(issueResponse.items as AutomationAnalyticsIssueRead[]);
      const nextId = snapshotId ?? nextSnapshots[0]?.id ?? null;
      if (!nextId) {
        setSelected(null);
        setMetrics([]);
        setTrends([]);
        setComparisons([]);
        return;
      }
      const [detail, metricResponse, trendResponse, comparisonResponse] = await Promise.all([
        apiClient.getAutomationAnalyticsSnapshot(nextId),
        apiClient.listAutomationAnalyticsMetrics({ snapshot_id: nextId, limit: 100, offset: 0 }),
        apiClient.listAutomationAnalyticsTrends({ snapshot_id: nextId, limit: 100, offset: 0 }),
        apiClient.listAutomationAnalyticsComparisons({ snapshot_id: nextId, limit: 100, offset: 0 }),
      ]);
      setSelected(detail);
      setMetrics(metricResponse.items as AutomationAnalyticsMetricRead[]);
      setTrends(trendResponse.items as AutomationAnalyticsTrendRead[]);
      setComparisons(comparisonResponse.items as AutomationAnalyticsComparisonRead[]);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation analytics workspace.");
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => {
    const latest = selected ?? snapshots[0] ?? null;
    const latestMetrics = metrics;
    return {
      queueThroughput: latestMetrics.find((row) => row.metric_key === "queue_throughput")?.metric_value ?? "0",
      workerUtilization: latestMetrics.find((row) => row.metric_key === "worker_utilization")?.metric_value ?? "0",
      failureRate: latestMetrics.find((row) => row.metric_key === "failure_rate")?.metric_value ?? "0",
      replayWarnings: latestMetrics.find((row) => row.metric_key === "replay_warning_count")?.metric_value ?? "0",
      deadLetter: latestMetrics.find((row) => row.metric_key === "dead_letter_growth")?.metric_value ?? "0",
      workflowThroughput: latestMetrics.find((row) => row.metric_key === "workflow_throughput")?.metric_value ?? "0",
      status: latest?.analytics_status ?? "—",
    };
  }, [metrics, selected, snapshots]);

  const manifestPreview = useMemo(() => {
    const manifest = selected?.snapshot_manifest_json;
    return manifest && typeof manifest === "object" ? JSON.stringify(manifest, null, 2) : null;
  }, [selected]);

  const timelineRows = useMemo(() => {
    const events = [
      ...trends.map((row) => ({ id: `t-${row.id}`, label: `Trend ${row.trend_type} ${row.trend_direction}`, created_at: row.created_at })),
      ...comparisons.map((row) => ({ id: `c-${row.id}`, label: `Comparison ${row.comparison_type}`, created_at: row.created_at })),
      ...issues.map((row) => ({ id: `i-${row.id}`, label: `Issue ${row.issue_type}`, created_at: row.created_at })),
    ];
    return events.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  }, [comparisons, issues, trends]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-09"
        title="Automation Analytics / Intelligence Layer"
        description="Deterministic replay-safe operational analytics infrastructure."
        actions={
          <Link to="/ops#automation-analytics-ops" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops diagnostics
          </Link>
        }
      />
      {error ? <div className="mt-4"><StatusBanner tone="error">{error}</StatusBanner></div> : null}
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading automation analytics workspace…</p>
      ) : !snapshots.length ? (
        <EmptyState title="No analytics snapshots yet" description="Analytics snapshots appear after an ops administrator creates deterministic analytics summaries." />
      ) : (
        <div className="mt-6 space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <StatCard label="Queue throughput" value={summary.queueThroughput} />
            <StatCard label="Worker utilization" value={summary.workerUtilization} />
            <StatCard label="Failure rate" value={summary.failureRate} />
            <StatCard label="Replay warnings" value={summary.replayWarnings} />
            <StatCard label="Dead-letter growth" value={summary.deadLetter} />
            <StatCard label="Workflow throughput" value={summary.workflowThroughput} />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Metrics panel">
              <ul className="space-y-2 text-xs text-slate-300">
                {metrics.map((row) => (
                  <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <span>{row.metric_category}/{row.metric_key}</span>
                      <span>{row.metric_status}</span>
                    </div>
                    <p className="mt-1 text-slate-400">{row.metric_value}{row.metric_delta ? ` · Δ ${row.metric_delta}` : ""}</p>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Trend panel">
              <ul className="space-y-2 text-xs text-slate-300">
                {trends.map((row) => (
                  <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                    {row.trend_type} · {row.trend_direction} · {row.trend_value}
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Historical comparison panel">
              <ul className="space-y-2 text-xs text-slate-300">
                {comparisons.map((row) => (
                  <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                    {row.comparison_type} · baseline #{row.baseline_snapshot_id ?? "—"}
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Replay intelligence panel">
              <ul className="space-y-2 text-xs text-slate-300">
                {issues.filter((row) => row.issue_type === "REPLAY_ANALYTICS_DRIFT").map((row) => (
                  <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                    {row.issue_type} · {row.severity} · {row.issue_message}
                  </li>
                ))}
              </ul>
            </Panel>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Issues panel">
              {issues.length ? (
                <ul className="space-y-2 text-xs text-slate-300">
                  {issues.slice(0, 12).map((row) => (
                    <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                      {row.issue_type} · {row.severity} · {row.issue_message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No analytics issues detected.</p>
              )}
            </Panel>
            <Panel title="Artifact panel">
              {manifestPreview ? (
                <pre className="max-h-80 overflow-auto rounded-2xl border border-white/5 bg-slate-950/50 p-3 text-[11px] text-slate-300">{manifestPreview}</pre>
              ) : (
                <p className="text-sm text-slate-500">Analytics manifest preview appears after the first snapshot.</p>
              )}
            </Panel>
          </div>

          <Panel title="History timeline">
            {timelineRows.length ? (
              <ul className="space-y-2 text-xs text-slate-300">
                {timelineRows.slice(0, 16).map((row) => (
                  <li key={row.id} className="rounded-2xl border border-white/5 bg-slate-950/40 px-3 py-2">
                    {formatDateTime(row.created_at)} · {row.label}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No analytics history yet.</p>
            )}
          </Panel>
        </div>
      )}
    </AppShell>
  );
}
