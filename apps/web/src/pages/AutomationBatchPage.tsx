import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AutomationBatchChunkRead,
  type AutomationBatchRunRead,
  type AutomationMaintenanceJobRead,
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

function statusTone(status: string): string {
  switch (status) {
    case "COMPLETED":
    case "PASS":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "RUNNING":
    case "QUEUED":
    case "RESERVED":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "FAILED":
    case "FAIL":
    case "PARTIALLY_COMPLETED":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
  }
}

export function AutomationBatchPage() {
  const [runs, setRuns] = useState<AutomationBatchRunRead[]>([]);
  const [maintenanceJobs, setMaintenanceJobs] = useState<AutomationMaintenanceJobRead[]>([]);
  const [selectedRun, setSelectedRun] = useState<AutomationBatchRunRead | null>(null);
  const [chunks, setChunks] = useState<AutomationBatchChunkRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void refreshBatchData();
  }, []);

  async function refreshBatchData(selectedId?: number | null): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [runResponse, maintenanceResponse] = await Promise.all([
        apiClient.listAutomationBatchRuns({ limit: 50, offset: 0 }),
        apiClient.listAutomationMaintenanceJobs({ limit: 50, offset: 0 }),
      ]);
      setRuns(runResponse.items);
      setMaintenanceJobs(maintenanceResponse.items);
      const nextId = selectedId ?? runResponse.items[0]?.id ?? null;
      if (nextId) {
        const [detail, chunkResponse] = await Promise.all([
          apiClient.getAutomationBatchRun(nextId),
          apiClient.listAutomationBatchChunks(nextId, { limit: 200, offset: 0 }),
        ]);
        setSelectedRun(detail);
        setChunks(chunkResponse.items);
      } else {
        setSelectedRun(null);
        setChunks([]);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation batch workspace.");
    } finally {
      setLoading(false);
    }
  }

  async function inspectBatch(batchId: number): Promise<void> {
    setError(null);
    try {
      const [detail, chunkResponse] = await Promise.all([
        apiClient.getAutomationBatchRun(batchId),
        apiClient.listAutomationBatchChunks(batchId, { limit: 200, offset: 0 }),
      ]);
      setSelectedRun(detail);
      setChunks(chunkResponse.items);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load batch detail.");
    }
  }

  const summary = useMemo(() => {
    const failed = runs.filter((row) => row.batch_status === "FAILED" || row.batch_status === "PARTIALLY_COMPLETED").length;
    const integrityAudits = maintenanceJobs.filter((row) => ["CHECKSUM_AUDIT", "LINEAGE_AUDIT", "QUEUE_INTEGRITY_CHECK"].includes(row.maintenance_type)).length;
    const orphanWarnings = maintenanceJobs.flatMap((row) => row.results).filter((row) => row.result_status === "WARNING").length;
    return { failed, integrityAudits, orphanWarnings };
  }, [maintenanceJobs, runs]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-05"
        title="Batch Processing / Maintenance Jobs"
        description="Deterministic replay-safe batch execution, maintenance audits, storage integrity checks, and operational batch diagnostics."
        actions={
          <div className="flex gap-2">
            <Link to="/automation-recovery" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Recovery layer
            </Link>
            <Link to="/ops#automation-batch-ops" className="rounded-2xl border border-amber-400/35 px-4 py-2 text-sm font-semibold text-amber-100">
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
        <StatCard label="Active batches" value={String(runs.length)} />
        <StatCard label="Failed batches" value={String(summary.failed)} />
        <StatCard label="Maintenance jobs" value={String(maintenanceJobs.length)} />
        <StatCard label="Integrity audits" value={String(summary.integrityAudits)} />
        <StatCard label="Orphan warnings" value={String(summary.orphanWarnings)} />
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Batch ledger">
          {loading ? (
            <p className="text-sm text-slate-600">Loading batch runs…</p>
          ) : runs.length ? (
            <div className="space-y-3">
              {runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => void inspectBatch(run.id)}
                  className="w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-sm text-left transition hover:border-amber-300/40"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">Batch #{run.id} · {run.batch_type}</p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(run.batch_status)}`}>
                      {run.batch_status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{run.source_scope} · checksum {shortenChecksum(run.batch_checksum)}</p>
                  <p className="mt-1 text-xs text-slate-500">Progress {run.completed_item_count}/{run.total_item_count} · failed {run.failed_item_count}</p>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="No batch runs yet" description="Batch runs appear here once automation workloads are partitioned into deterministic chunks." />
          )}
        </Panel>

        <Panel title="Chunk visualization">
          {chunks.length ? (
            <div className="space-y-3">
              {chunks.map((chunk) => (
                <div key={chunk.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">Chunk #{chunk.chunk_rank}</p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(chunk.chunk_status)}`}>
                      {chunk.chunk_status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{chunk.item_start} - {chunk.item_end} · {chunk.item_count} items</p>
                  <p className="mt-1 text-xs text-slate-500">Partition {chunk.partition_key} · checksum {shortenChecksum(chunk.chunk_checksum)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Select a batch run to inspect its deterministic chunk layout.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Maintenance panel">
          {maintenanceJobs.length ? (
            <div className="space-y-3">
              {maintenanceJobs.map((job) => (
                <div key={job.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">{job.maintenance_type}</p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(job.maintenance_status)}`}>
                      {job.maintenance_status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{job.maintenance_scope}</p>
                  <p className="mt-1 text-xs text-slate-500">Started {formatDateTime(job.started_at)} · checksum {shortenChecksum(job.maintenance_checksum)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">No maintenance jobs recorded yet.</p>
          )}
        </Panel>

        <Panel title="Integrity audit panel">
          {maintenanceJobs.length ? (
            <div className="space-y-3">
              {maintenanceJobs
                .filter((job) => ["CHECKSUM_AUDIT", "LINEAGE_AUDIT", "QUEUE_INTEGRITY_CHECK", "STORAGE_AUDIT"].includes(job.maintenance_type))
                .map((job) => (
                  <div key={job.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                    <p className="text-sm font-semibold text-slate-900">{job.maintenance_type}</p>
                    <p className="mt-1 text-xs text-slate-400">
                      {job.results.map((result) => `${result.result_type}:${result.result_status}`).join(" · ") || "No results"}
                    </p>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Integrity audit visibility appears here once maintenance jobs have run.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Issues panel">
          {selectedRun?.issues.length ? (
            <div className="space-y-3">
              {selectedRun.issues.map((issue) => (
                <div key={issue.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-slate-900">{issue.issue_type}</p>
                  <p className="mt-1 text-xs text-slate-400">{issue.issue_message}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">No batch issues are visible for the selected run.</p>
          )}
        </Panel>

        <Panel title="Artifact panel">
          {selectedRun?.artifacts.length ? (
            <div className="space-y-3">
              {selectedRun.artifacts.map((artifact) => (
                <div key={artifact.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-slate-900">{artifact.artifact_type}</p>
                  <p className="mt-1 break-all text-xs text-slate-400">{artifact.storage_path}</p>
                  <p className="mt-1 text-xs text-slate-500">Checksum {shortenChecksum(artifact.artifact_checksum)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Batch artifacts appear here once a run is selected.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6">
        <Panel title="History timeline">
          {selectedRun?.history.length ? (
            <div className="space-y-3">
              {selectedRun.history.map((entry) => (
                <div key={entry.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-slate-900">{entry.event_type}</p>
                  <p className="mt-1 text-xs text-slate-400">{entry.event_message}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatDateTime(entry.created_at)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Append-only batch events appear here once a run is selected.</p>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
