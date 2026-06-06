import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AutomationDeadLetterRead,
  type AutomationFailureEventRead,
  type AutomationRecoveryRunRead,
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
    case "RESOLVED":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "RUNNING":
    case "ACTIVE":
    case "REPLAY_PENDING":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "FAILED":
    case "BLOCKED":
    case "CRITICAL":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
  }
}

export function AutomationRecoveryPage() {
  const [runs, setRuns] = useState<AutomationRecoveryRunRead[]>([]);
  const [deadLetter, setDeadLetter] = useState<AutomationDeadLetterRead[]>([]);
  const [failures, setFailures] = useState<AutomationFailureEventRead[]>([]);
  const [selectedRun, setSelectedRun] = useState<AutomationRecoveryRunRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void refreshRecoveryData();
  }, []);

  async function refreshRecoveryData(selectedId?: number | null): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [runResponse, deadLetterResponse, failureResponse] = await Promise.all([
        apiClient.listAutomationRecoveryRuns({ limit: 50, offset: 0 }),
        apiClient.listAutomationDeadLetterJobs({ limit: 50, offset: 0 }),
        apiClient.listAutomationFailureEvents({ limit: 50, offset: 0 }),
      ]);
      setRuns(runResponse.items);
      setDeadLetter(deadLetterResponse.items);
      setFailures(failureResponse.items);
      const nextId = selectedId ?? runResponse.items[0]?.id ?? null;
      if (nextId) {
        const detail = await apiClient.getAutomationRecoveryRun(nextId);
        setSelectedRun(detail);
      } else {
        setSelectedRun(null);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation recovery workspace.");
    } finally {
      setLoading(false);
    }
  }

  async function inspectRun(runId: number): Promise<void> {
    setError(null);
    try {
      const detail = await apiClient.getAutomationRecoveryRun(runId);
      setSelectedRun(detail);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load recovery detail.");
    }
  }

  const summary = useMemo(() => {
    const retries = runs.filter((row) => row.recovery_type === "RETRY").length;
    const staleExecutions = failures.filter((row) => row.failure_type === "HEARTBEAT_LOSS" || row.failure_type === "LEASE_TIMEOUT").length;
    const critical = failures.filter((row) => row.failure_severity === "CRITICAL").length;
    return { retries, staleExecutions, critical };
  }, [failures, runs]);

  const replayJobChecksum = useMemo(() => {
    const replayReferences = selectedRun?.recovery_manifest_json?.replay_references;
    if (!replayReferences || typeof replayReferences !== "object") {
      return "";
    }
    return String((replayReferences as Record<string, unknown>).replay_job_checksum ?? "");
  }, [selectedRun]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-04"
        title="Retry / Failure / Dead-Letter / Replay Recovery"
        description="Deterministic replay-safe automation recovery for retries, dead-letter routing, stale execution recovery, failure lineage, and recovery diagnostics."
        actions={
          <div className="flex gap-2">
            <Link to="/automation-workflows" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Workflow orchestration
            </Link>
            <Link to="/ops#automation-recovery-ops" className="rounded-2xl border border-rose-400/35 px-4 py-2 text-sm font-semibold text-rose-100">
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
        <StatCard label="Failed jobs" value={String(failures.length)} />
        <StatCard label="Retries pending" value={String(summary.retries)} />
        <StatCard label="Dead-letter count" value={String(deadLetter.length)} />
        <StatCard label="Stale executions" value={String(summary.staleExecutions)} />
        <StatCard label="Critical failures" value={String(summary.critical)} />
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Recovery ledger">
          {loading ? (
            <p className="text-sm text-slate-600">Loading recovery ledger…</p>
          ) : runs.length ? (
            <div className="space-y-3">
              {runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => void inspectRun(run.id)}
                  className="w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-sm text-left transition hover:border-rose-300/40"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">
                      Recovery #{run.id} · job #{run.job_id}
                    </p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(run.recovery_status)}`}>
                      {run.recovery_status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{run.recovery_type} · checksum {shortenChecksum(run.recovery_checksum)}</p>
                  <p className="mt-1 text-xs text-slate-500">Started {formatDateTime(run.started_at)} · Rank {run.recovery_rank}</p>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="No recovery runs yet" description="Recovery runs will appear here once retries, dead-letter transfers, stale execution recovery, or replay recovery are triggered." />
          )}
        </Panel>

        <Panel title="Dead-letter queue">
          {deadLetter.length ? (
            <div className="space-y-3">
              {deadLetter.map((row) => (
                <div key={row.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">Job #{row.original_job_id}</p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(row.dead_letter_status)}`}>
                      {row.dead_letter_status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{row.dead_letter_reason}</p>
                  <p className="mt-1 text-xs text-slate-500">Failures {row.failure_count} · checksum {shortenChecksum(row.dead_letter_checksum)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">No dead-letter jobs recorded yet.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Failure event table">
          {failures.length ? (
            <div className="space-y-3">
              {failures.map((failure) => (
                <div key={failure.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">{failure.failure_type}</p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(failure.failure_severity)}`}>
                      {failure.failure_severity}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">Job #{failure.job_id ?? "—"} · Execution #{failure.worker_execution_id ?? "—"}</p>
                  <p className="mt-1 text-xs text-slate-500">Captured {formatDateTime(failure.created_at)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">No failure events have been captured yet.</p>
          )}
        </Panel>

        <Panel title="Replay recovery panel">
          {selectedRun ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-sm font-semibold text-slate-900">Replay lineage</p>
              <p className="mt-1 text-xs text-slate-400">
                Replay references {shortenChecksum(replayJobChecksum)}
              </p>
              <p className="mt-2 text-xs text-slate-500">Dead-letter state {selectedRun.dead_letter?.dead_letter_status ?? "—"}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-600">Select a recovery run to inspect replay recovery lineage.</p>
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
            <p className="text-sm text-slate-600">No recovery issues are visible for the selected run.</p>
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
            <p className="text-sm text-slate-600">Recovery artifacts appear here once a run is selected.</p>
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
            <p className="text-sm text-slate-600">Append-only recovery history appears here once a run is selected.</p>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
