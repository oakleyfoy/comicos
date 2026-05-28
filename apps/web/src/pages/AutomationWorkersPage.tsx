import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AutomationWorkerDetail,
  type AutomationWorkerExecutionRead,
  type AutomationWorkerRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function shortenChecksum(value?: string | null): string {
  if (!value) return "—";
  if (value.length <= 18) return value;
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
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

function statusTone(status: string): string {
  switch (status) {
    case "IDLE":
    case "COMPLETED":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "RUNNING":
    case "RESERVED":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "ERROR":
    case "FAILED":
    case "TIMED_OUT":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
  }
}

export function AutomationWorkersPage() {
  const [workers, setWorkers] = useState<AutomationWorkerRead[]>([]);
  const [selectedWorker, setSelectedWorker] = useState<AutomationWorkerDetail | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<AutomationWorkerExecutionRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [staleWorkers, setStaleWorkers] = useState<AutomationWorkerRead[]>([]);

  useEffect(() => {
    void refreshWorkers();
  }, []);

  async function refreshWorkers(selectedId?: number | null): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [workerResponse, staleResponse] = await Promise.all([
        apiClient.listAutomationWorkers({ limit: 50, offset: 0 }),
        apiClient.listOpsAutomationStaleWorkers({ limit: 25, offset: 0 }),
      ]);
      setWorkers(workerResponse.items);
      setStaleWorkers(staleResponse.items);
      const nextId = selectedId ?? workerResponse.items[0]?.id ?? null;
      if (nextId) {
        const detail = await apiClient.getAutomationWorker(nextId);
        setSelectedWorker(detail);
        setSelectedExecution(detail.executions[0] ?? null);
      } else {
        setSelectedWorker(null);
        setSelectedExecution(null);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation worker runtime.");
    } finally {
      setLoading(false);
    }
  }

  async function inspectWorker(workerId: number): Promise<void> {
    setError(null);
    try {
      const detail = await apiClient.getAutomationWorker(workerId);
      setSelectedWorker(detail);
      setSelectedExecution(detail.executions[0] ?? null);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load worker detail.");
    }
  }

  const summary = useMemo(() => {
    const active = workers.reduce((sum, row) => sum + row.active_execution_count, 0);
    const leases = workers.reduce((sum, row) => sum + row.active_lease_count, 0);
    const failed = selectedWorker?.executions.filter((row) => row.execution_status === "FAILED").length ?? 0;
    const overloaded = workers.filter((row) => row.worker_status === "ERROR").length;
    return { active, leases, failed, overloaded };
  }, [selectedWorker?.executions, workers]);

  const selectedExecutionArtifacts = useMemo(() => {
    const refs = selectedExecution?.execution_snapshot_json?.artifact_refs;
    return Array.isArray(refs) ? refs : [];
  }, [selectedExecution]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-02"
        title="Worker Runtime Engine"
        description="Deterministic replay-safe worker execution runtime for leases, heartbeats, execution lineage, timeout visibility, and append-only runtime history."
        actions={
          <div className="flex gap-2">
            <Link to="/automation-jobs" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Queue foundation
            </Link>
            <Link to="/ops#automation-worker-ops" className="rounded-2xl border border-violet-400/35 px-4 py-2 text-sm font-semibold text-violet-100">
              Ops diagnostics
            </Link>
          </div>
        }
      />
      {error ? (
        <div className="mt-4">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Active workers" value={String(workers.length)} />
        <StatCard label="Stale workers" value={String(staleWorkers.length)} />
        <StatCard label="Active leases" value={String(summary.leases)} />
        <StatCard label="Failed executions" value={String(summary.failed)} />
        <StatCard label="Errored workers" value={String(summary.overloaded)} />
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Worker table">
          {loading ? (
            <p className="text-sm text-slate-400">Loading automation workers…</p>
          ) : workers.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm text-slate-300">
                <thead className="text-xs uppercase tracking-[0.14em] text-slate-500">
                  <tr>
                    <th className="pb-3 pr-4">Worker</th>
                    <th className="pb-3 pr-4">Status</th>
                    <th className="pb-3 pr-4">Queue scope</th>
                    <th className="pb-3 pr-4">Current job</th>
                    <th className="pb-3 pr-4">Heartbeat age</th>
                    <th className="pb-3">Concurrency</th>
                  </tr>
                </thead>
                <tbody>
                  {workers.map((worker) => (
                    <tr
                      key={worker.id}
                      className="cursor-pointer border-t border-white/5 align-top transition hover:bg-white/5"
                      onClick={() => void inspectWorker(worker.id)}
                    >
                      <td className="py-3 pr-4">
                        <p className="font-medium text-white">{worker.worker_identifier}</p>
                        <p className="text-xs text-slate-500">{worker.worker_type}</p>
                      </td>
                      <td className="py-3 pr-4">
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(worker.worker_status)}`}>
                          {worker.worker_status}
                        </span>
                      </td>
                      <td className="py-3 pr-4">
                        {Array.isArray(worker.queue_scope_json.queue_keys)
                          ? (worker.queue_scope_json.queue_keys as string[]).join(", ")
                          : "all queues"}
                      </td>
                      <td className="py-3 pr-4">{worker.current_job_id ? `#${worker.current_job_id}` : "—"}</td>
                      <td className="py-3 pr-4">{worker.heartbeat_age_seconds ?? "stale"}</td>
                      <td className="py-3">{worker.active_execution_count}/{worker.max_concurrency}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No worker runtime activity yet" description="Workers appear here once the ops runtime registers them and begins acquiring leases from the automation queue." />
          )}
        </Panel>

        <Panel title="Lease panel">
          {selectedWorker?.leases.length ? (
            <div className="space-y-3">
              {selectedWorker.leases.map((lease) => (
                <div key={lease.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">Job #{lease.job_id} · {lease.lease_status}</p>
                  <p className="mt-1 text-xs text-slate-400">Token {lease.reservation_token}</p>
                  <p className="mt-1 text-xs text-slate-500">Expires {formatDateTime(lease.lease_expires_at)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No worker leases recorded yet.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Execution ledger">
          {selectedWorker?.executions.length ? (
            <div className="space-y-3">
              {selectedWorker.executions.map((execution) => (
                <button
                  key={execution.id}
                  type="button"
                  onClick={() => setSelectedExecution(execution)}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/45 p-4 text-left transition hover:border-violet-300/40"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-white">Execution #{execution.id} · job #{execution.job_id}</p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(execution.execution_status)}`}>
                      {execution.execution_status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">Checksum {shortenChecksum(execution.execution_checksum)}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    Started {formatDateTime(execution.started_at)} · Duration {execution.execution_time_ms ?? "—"} ms
                  </p>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No worker executions available yet.</p>
          )}
        </Panel>

        <Panel title="Issues panel">
          {selectedWorker?.issues.length ? (
            <div className="space-y-3">
              {selectedWorker.issues.map((issue) => (
                <div key={issue.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">{issue.issue_type} · {issue.severity}</p>
                  <p className="mt-1 text-xs text-slate-400">{issue.issue_message}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No worker issues recorded for the selected runtime.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Panel title="Artifact panel">
          {selectedExecution ? (
            <div className="space-y-3">
              <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                <p className="text-sm font-semibold text-white">Execution snapshot</p>
                <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-2xl bg-slate-950/70 p-3 text-xs text-slate-300">
                  {JSON.stringify(selectedExecution.execution_snapshot_json, null, 2)}
                </pre>
              </div>
              {selectedExecutionArtifacts.length ? (
                <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">Stored artifact refs</p>
                  <div className="mt-3 space-y-2">
                    {selectedExecutionArtifacts.map((artifact, index) => (
                      <div key={`${index}-${String((artifact as Record<string, unknown>).artifact_type ?? "artifact")}`} className="rounded-xl border border-white/5 p-3 text-xs text-slate-300">
                        <p>{String((artifact as Record<string, unknown>).artifact_type ?? "artifact")}</p>
                        <p className="mt-1 text-slate-500">{String((artifact as Record<string, unknown>).storage_path ?? "—")}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Select an execution to inspect its immutable runtime snapshot and artifact refs.</p>
          )}
        </Panel>

        <Panel title="History timeline">
          {selectedWorker?.history.length ? (
            <div className="space-y-3">
              {selectedWorker.history.map((event) => (
                <div key={event.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-white">{event.event_type}</p>
                    <p className="text-xs text-slate-500">{formatDateTime(event.created_at)}</p>
                  </div>
                  <p className="mt-1 text-sm text-slate-300">{event.event_message}</p>
                  <p className="mt-2 text-xs text-slate-500">
                    {event.from_status ?? "—"} → {event.to_status ?? "—"} · {shortenChecksum(event.event_checksum)}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Append-only worker/runtime history will appear here as heartbeats, leases, and executions are recorded.</p>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
