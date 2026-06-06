import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AutomationOpsAuditRead,
  type AutomationOpsIssueRead,
  type AutomationOpsMetricRead,
  type AutomationOpsSnapshotRead,
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
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
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

export function AutomationOpsDashboardPage() {
  const [snapshots, setSnapshots] = useState<AutomationOpsSnapshotRead[]>([]);
  const [metrics, setMetrics] = useState<AutomationOpsMetricRead[]>([]);
  const [audits, setAudits] = useState<AutomationOpsAuditRead[]>([]);
  const [issues, setIssues] = useState<AutomationOpsIssueRead[]>([]);
  const [selected, setSelected] = useState<AutomationOpsSnapshotRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void refresh();
  }, []);

  async function refresh(snapshotId?: number | null): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [snapshotResponse, auditResponse, issueResponse] = await Promise.all([
        apiClient.listAutomationOpsSnapshots({ limit: 50, offset: 0 }),
        apiClient.listAutomationOpsAudits({ limit: 50, offset: 0 }),
        apiClient.listAutomationOpsIssues({ limit: 50, offset: 0 }),
      ]);
      setSnapshots(snapshotResponse.items as AutomationOpsSnapshotRead[]);
      setAudits(auditResponse.items as AutomationOpsAuditRead[]);
      setIssues(issueResponse.items as AutomationOpsIssueRead[]);
      const nextId = snapshotId ?? snapshotResponse.items[0]?.id ?? null;
      if (nextId) {
        const detail = await apiClient.getAutomationOpsSnapshot(nextId);
        setSelected(detail);
        const metricResponse = await apiClient.listAutomationOpsMetrics({ snapshot_id: nextId, limit: 100, offset: 0 });
        setMetrics(metricResponse.items as AutomationOpsMetricRead[]);
      } else {
        setSelected(null);
        setMetrics([]);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load ops automation dashboard.");
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => {
    const latest = selected ?? snapshots[0] ?? null;
    return {
      queueDepth: latest?.queue_depth ?? 0,
      activeWorkers: latest?.active_workers ?? 0,
      failedJobs: latest?.failed_jobs ?? 0,
      deadLetter: latest?.dead_letter_count ?? 0,
      replayWarnings: latest?.replay_warning_count ?? 0,
      checksumWarnings: latest?.checksum_warning_count ?? 0,
      status: latest?.snapshot_status ?? "—",
    };
  }, [selected, snapshots]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-07"
        title="Ops Automation Dashboard / Admin Controls"
        description="Deterministic replay-safe operational control center."
        actions={
          <Link to="/ops#automation-ops-dashboard" className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200">
            Open ops console
          </Link>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading ops automation dashboard…</p>
      ) : !snapshots.length ? (
        <EmptyState title="No ops snapshots yet" description="Ops snapshots appear after an administrator creates system health snapshots." />
      ) : (
        <div className="mt-6 space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <StatCard label="Queue depth" value={String(summary.queueDepth)} />
            <StatCard label="Active workers" value={String(summary.activeWorkers)} />
            <StatCard label="Failed jobs" value={String(summary.failedJobs)} />
            <StatCard label="Dead letter" value={String(summary.deadLetter)} />
            <StatCard label="Replay warnings" value={String(summary.replayWarnings)} />
            <StatCard label="Checksum warnings" value={String(summary.checksumWarnings)} />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Panel title="Queue health">
              <p className="text-sm text-slate-300">System status: {summary.status}</p>
              <ul className="mt-2 space-y-1 text-xs text-slate-400">
                {metrics.filter((row) => row.metric_category === "QUEUE").map((row) => (
                  <li key={row.id}>
                    {row.metric_key}: {row.metric_value} ({row.metric_status})
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Worker runtime">
              <ul className="space-y-1 text-xs text-slate-400">
                {metrics.filter((row) => row.metric_category === "WORKER").map((row) => (
                  <li key={row.id}>
                    {row.metric_key}: {row.metric_value} ({row.metric_status})
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Replay integrity">
              <ul className="space-y-1 text-xs text-slate-400">
                {metrics.filter((row) => row.metric_category === "REPLAY").map((row) => (
                  <li key={row.id}>
                    {row.metric_key}: {row.metric_value}
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Recovery / batch / notifications">
              <ul className="space-y-1 text-xs text-slate-400">
                {metrics
                  .filter((row) => ["RECOVERY", "BATCH", "NOTIFICATION"].includes(row.metric_category))
                  .map((row) => (
                    <li key={row.id}>
                      {row.metric_category}/{row.metric_key}: {row.metric_value}
                    </li>
                  ))}
              </ul>
            </Panel>
          </div>

          <Panel title="Audit results">
            {audits.length ? (
              <ul className="space-y-2 text-xs text-slate-300">
                {audits.slice(0, 12).map((row) => (
                  <li key={row.id} className="rounded-xl border border-white/5 bg-slate-950/40 px-3 py-2">
                    {row.audit_type} · {row.audit_status} · {formatDateTime(row.created_at)}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No audits recorded.</p>
            )}
          </Panel>

          <Panel title="Operational issues">
            {issues.length ? (
              <ul className="space-y-2 text-xs text-slate-300">
                {issues.slice(0, 16).map((row) => (
                  <li key={row.id} className="rounded-xl border border-white/5 bg-slate-950/40 px-3 py-2">
                    <span className="font-semibold text-amber-800">{row.issue_type}</span> · {row.severity} · {row.issue_message}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No issues detected for visible snapshots.</p>
            )}
          </Panel>

          <Panel title="Snapshot lineage">
            {selected ? (
              <dl className="grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
                <div>
                  <dt className="text-slate-500">Snapshot</dt>
                  <dd className="text-slate-200">#{selected.id} · {selected.snapshot_type}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Checksum</dt>
                  <dd className="font-mono text-[11px] text-slate-200">{selected.snapshot_checksum.slice(0, 24)}…</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Created</dt>
                  <dd>{formatDateTime(selected.created_at)}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Replay safe</dt>
                  <dd>{selected.replay_safe ? "yes" : "no"}</dd>
                </div>
              </dl>
            ) : null}
          </Panel>

          <Panel title="Safe admin controls">
            <p className="text-sm text-slate-600">
              Pause queue, resume queue, acknowledge alerts, maintenance lock, and replay verify are available from the ops console. Destructive controls are not exposed.
            </p>
          </Panel>
        </div>
      )}
    </AppShell>
  );
}
