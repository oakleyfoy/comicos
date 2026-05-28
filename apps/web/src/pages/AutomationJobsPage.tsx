import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AutomationJobArtifactRead,
  type AutomationJobCreate,
  type AutomationJobDetail,
  type AutomationJobRead,
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
    case "COMPLETED":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "FAILED":
    case "DEAD_LETTER":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    case "RESERVED":
    case "RUNNING":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "CANCELLED":
      return "border-slate-400/35 bg-slate-400/10 text-slate-100";
    default:
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
  }
}

type QueueCategory = AutomationJobCreate["queue_category"];
type JobPriority = AutomationJobCreate["priority"];

const queueCategories: QueueCategory[] = ["SCAN_PIPELINE", "REPLAY", "NOTIFICATION", "MAINTENANCE", "BATCH", "REVIEW", "SYSTEM"];
const priorities: JobPriority[] = ["LOW", "NORMAL", "HIGH", "CRITICAL"];

const queueDefaults: Record<QueueCategory, { queueKey: string; jobType: string }> = {
  SCAN_PIPELINE: { queueKey: "scan-pipeline", jobType: "SCAN_PIPELINE_RUN" },
  REPLAY: { queueKey: "replay", jobType: "REPLAY_RUN" },
  NOTIFICATION: { queueKey: "notification", jobType: "FUTURE_RESERVED" },
  MAINTENANCE: { queueKey: "maintenance", jobType: "SYSTEM_MAINTENANCE" },
  BATCH: { queueKey: "batch", jobType: "FUTURE_RESERVED" },
  REVIEW: { queueKey: "review", jobType: "REVIEW_EXPORT" },
  SYSTEM: { queueKey: "system", jobType: "SYSTEM_MAINTENANCE" },
};

export function AutomationJobsPage() {
  const [jobs, setJobs] = useState<AutomationJobRead[]>([]);
  const [selectedJob, setSelectedJob] = useState<AutomationJobDetail | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<AutomationJobArtifactRead | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingArtifactId, setLoadingArtifactId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    queue_category: "REPLAY" as QueueCategory,
    queue_key: "replay",
    job_key: "replay-run-001",
    job_type: "REPLAY_RUN",
    priority: "NORMAL" as JobPriority,
    payload_json: JSON.stringify({ replay_scope: "FULL_P40_PIPELINE", scan_image_id: 1 }, null, 2),
  });

  useEffect(() => {
    void refreshJobs();
  }, []);

  async function refreshJobs(selectedId?: number | null): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.listAutomationJobs({ limit: 50, offset: 0 });
      setJobs(response.items);
      const nextId = selectedId ?? response.items[0]?.id ?? null;
      if (nextId) {
        const detail = await apiClient.getAutomationJob(nextId);
        setSelectedJob(detail);
      } else {
        setSelectedJob(null);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation queue workspace.");
    } finally {
      setLoading(false);
    }
  }

  async function submitJob(): Promise<void> {
    setSubmitting(true);
    setError(null);
    try {
      const parsedPayload = JSON.parse(form.payload_json) as Record<string, unknown>;
      const detail = await apiClient.createAutomationJob({
        queue_key: form.queue_key,
        queue_category: form.queue_category,
        job_key: form.job_key,
        job_type: form.job_type,
        priority: form.priority,
        payload_snapshot_json: parsedPayload,
        replay_safe: true,
        max_attempts: 3,
      });
      setSelectedJob(detail);
      setSelectedArtifact(null);
      await refreshJobs(detail.id);
    } catch (submitErr) {
      setError(submitErr instanceof ApiError ? submitErr.message : "Unable to create automation job.");
    } finally {
      setSubmitting(false);
    }
  }

  async function inspectJob(jobId: number): Promise<void> {
    setError(null);
    try {
      const detail = await apiClient.getAutomationJob(jobId);
      setSelectedJob(detail);
      setSelectedArtifact(null);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation job detail.");
    }
  }

  async function inspectArtifact(jobId: number, artifactId: number): Promise<void> {
    setLoadingArtifactId(artifactId);
    try {
      const artifact = await apiClient.getAutomationJobArtifact(jobId, artifactId);
      setSelectedArtifact(artifact);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load automation artifact.");
    } finally {
      setLoadingArtifactId(null);
    }
  }

  function downloadArtifact(artifact: AutomationJobArtifactRead): void {
    const body = artifact.body_base64 ? atob(artifact.body_base64) : artifact.text_preview ?? "";
    const bytes = Uint8Array.from(body, (char) => char.charCodeAt(0));
    const blob = new Blob([bytes], { type: artifact.media_type ?? "application/octet-stream" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = artifact.storage_path.split("/").pop() || `${artifact.artifact_type.toLowerCase()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const summary = useMemo(() => {
    const failed = jobs.filter((row) => row.job_status === "FAILED").length;
    const deadLetter = jobs.filter((row) => row.job_status === "DEAD_LETTER").length;
    const reserved = jobs.filter((row) => row.job_status === "RESERVED").length;
    const pending = jobs.filter((row) => ["PENDING", "AVAILABLE", "RETRY_PENDING"].includes(row.job_status)).length;
    const queueCount = new Set(jobs.map((row) => row.queue_key ?? row.queue_id)).size;
    return { failed, deadLetter, reserved, pending, queueCount };
  }, [jobs]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-01"
        title="Automation Queue Foundation"
        description="Deterministic replay-safe job ledger and queue system for future orchestration, retry metadata, queue lineage, and worker-safe reservations."
        actions={
          <div className="flex gap-2">
            <Link to="/dashboard" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Dashboard
            </Link>
            <Link to="/ops#automation-queue-ops" className="rounded-2xl border border-fuchsia-400/35 px-4 py-2 text-sm font-semibold text-fuchsia-100">
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

      <section className="mt-6 rounded-3xl border border-white/10 bg-slate-900/65 p-5">
        <div className="grid gap-4 xl:grid-cols-[1.15fr,0.85fr]">
          <div className="space-y-4">
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">Job creation</p>
              <h2 className="mt-1 text-lg font-semibold text-white">Create deterministic ledger entries</h2>
              <p className="mt-1 text-sm text-slate-400">
                Queue creation is durable and replay-safe only. This workspace does not execute workers or schedule jobs.
              </p>
            </div>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <label className="space-y-2 text-sm text-slate-300">
                <span>Queue category</span>
                <select
                  value={form.queue_category}
                  onChange={(event) => {
                    const nextCategory = event.target.value as QueueCategory;
                    setForm((current) => ({
                      ...current,
                      queue_category: nextCategory,
                      queue_key: queueDefaults[nextCategory].queueKey,
                      job_type: queueDefaults[nextCategory].jobType,
                    }));
                  }}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                >
                  {queueCategories.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-slate-300">
                <span>Queue key</span>
                <input
                  value={form.queue_key}
                  onChange={(event) => setForm((current) => ({ ...current, queue_key: event.target.value }))}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
              </label>
              <label className="space-y-2 text-sm text-slate-300">
                <span>Priority</span>
                <select
                  value={form.priority}
                  onChange={(event) => setForm((current) => ({ ...current, priority: event.target.value as JobPriority }))}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                >
                  {priorities.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-2 text-sm text-slate-300">
                <span>Job key</span>
                <input
                  value={form.job_key}
                  onChange={(event) => setForm((current) => ({ ...current, job_key: event.target.value }))}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
              </label>
              <label className="space-y-2 text-sm text-slate-300">
                <span>Job type</span>
                <input
                  value={form.job_type}
                  onChange={(event) => setForm((current) => ({ ...current, job_type: event.target.value }))}
                  className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white"
                />
              </label>
            </div>
            <label className="block space-y-2 text-sm text-slate-300">
              <span>Payload snapshot JSON</span>
              <textarea
                rows={8}
                value={form.payload_json}
                onChange={(event) => setForm((current) => ({ ...current, payload_json: event.target.value }))}
                className="w-full rounded-2xl border border-white/10 bg-slate-950/60 px-3 py-2 font-mono text-xs text-white"
              />
            </label>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => void submitJob()}
                disabled={submitting}
                className="rounded-2xl bg-fuchsia-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-fuchsia-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Creating…" : "Create automation job"}
              </button>
              <p className="text-xs text-slate-500">Creation writes immutable payload and manifest artifacts with deterministic checksums.</p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
            <StatCard label="Active queues" value={String(summary.queueCount)} />
            <StatCard label="Pending jobs" value={String(summary.pending)} />
            <StatCard label="Failed jobs" value={String(summary.failed)} />
            <StatCard label="Dead-letter / reserved" value={`${summary.deadLetter} / ${summary.reserved}`} />
          </div>
        </div>
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.25fr,0.75fr]">
        <Panel title="Job table">
          {loading ? (
            <p className="text-sm text-slate-400">Loading automation jobs…</p>
          ) : jobs.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm text-slate-300">
                <thead className="text-xs uppercase tracking-[0.14em] text-slate-500">
                  <tr>
                    <th className="pb-3 pr-4">Job</th>
                    <th className="pb-3 pr-4">Status</th>
                    <th className="pb-3 pr-4">Priority</th>
                    <th className="pb-3 pr-4">Rank</th>
                    <th className="pb-3 pr-4">Queue</th>
                    <th className="pb-3 pr-4">Reservation</th>
                    <th className="pb-3">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr
                      key={job.id}
                      className="cursor-pointer border-t border-white/5 align-top transition hover:bg-white/5"
                      onClick={() => void inspectJob(job.id)}
                    >
                      <td className="py-3 pr-4">
                        <p className="font-medium text-white">{job.job_type}</p>
                        <p className="text-xs text-slate-500">{job.job_key}</p>
                      </td>
                      <td className="py-3 pr-4">
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(job.job_status)}`}>
                          {job.job_status}
                        </span>
                      </td>
                      <td className="py-3 pr-4">{job.priority}</td>
                      <td className="py-3 pr-4">{job.deterministic_rank}</td>
                      <td className="py-3 pr-4">{job.queue_key ?? `#${job.queue_id}`}</td>
                      <td className="py-3 pr-4">{job.reservation_token ? "Reserved" : "Idle"}</td>
                      <td className="py-3">{formatDateTime(job.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No automation jobs yet" description="Create a deterministic queue job to populate the ledger, history timeline, dependencies, and artifact manifest panels." />
          )}
        </Panel>

        <Panel title="Queue summary">
          <div className="space-y-3">
            {Object.entries(
              jobs.reduce<Record<string, number>>((acc, job) => {
                const key = job.queue_key ?? `queue-${job.queue_id}`;
                acc[key] = (acc[key] ?? 0) + 1;
                return acc;
              }, {}),
            )
              .sort((left, right) => left[0].localeCompare(right[0]))
              .map(([queueKey, count]) => (
                <div key={queueKey} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">{queueKey}</p>
                  <p className="mt-1 text-xs text-slate-400">{count} deterministic ledger entries</p>
                </div>
              ))}
            {!jobs.length ? <p className="text-sm text-slate-400">Queue health appears here once jobs exist.</p> : null}
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Panel title="Dependency panel">
          {selectedJob?.dependencies.length ? (
            <div className="space-y-3">
              {selectedJob.dependencies.map((dependency) => (
                <div key={dependency.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">
                    Job #{dependency.job_id} depends on #{dependency.depends_on_job_id}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{dependency.dependency_status}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">Selected job has no registered dependency edges yet.</p>
          )}
        </Panel>

        <Panel title="Attempt history panel">
          {selectedJob?.attempts.length ? (
            <div className="space-y-3">
              {selectedJob.attempts.map((attempt) => (
                <div key={attempt.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">
                    Attempt {attempt.attempt_number} · {attempt.attempt_status}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Worker {attempt.worker_identifier ?? "—"} · {attempt.execution_time_ms ?? "—"} ms
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No worker attempts yet. This phase stores the foundation but does not execute jobs.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Panel title="Issues panel">
          {selectedJob?.issues.length ? (
            <div className="space-y-3">
              {selectedJob.issues.map((issue) => (
                <div key={issue.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-white">
                    {issue.issue_type} · {issue.severity}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">{issue.issue_message}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No queue issues recorded for the selected job.</p>
          )}
        </Panel>

        <Panel title="Artifact panel">
          {selectedJob?.artifacts.length ? (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {selectedJob.artifacts.map((artifact) => (
                  <button
                    key={artifact.id}
                    type="button"
                    onClick={() => void inspectArtifact(selectedJob.id, artifact.id)}
                    className="rounded-full border border-white/10 px-3 py-1.5 text-xs font-semibold text-slate-200 transition hover:border-fuchsia-300/40 hover:text-white"
                  >
                    {loadingArtifactId === artifact.id ? "Loading…" : artifact.artifact_type}
                  </button>
                ))}
              </div>
              {selectedArtifact ? (
                <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">{selectedArtifact.artifact_type}</p>
                      <p className="mt-1 text-xs text-slate-500">{selectedArtifact.storage_path}</p>
                      <p className="mt-1 text-xs text-slate-500">Checksum {shortenChecksum(selectedArtifact.artifact_checksum)}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => downloadArtifact(selectedArtifact)}
                      className="rounded-full border border-fuchsia-400/35 px-3 py-1.5 text-xs font-semibold text-fuchsia-100"
                    >
                      Download
                    </button>
                  </div>
                  <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-2xl bg-slate-950/70 p-3 text-xs text-slate-300">
                    {selectedArtifact.text_preview ?? "Binary artifact preview unavailable."}
                  </pre>
                </div>
              ) : (
                <p className="text-sm text-slate-400">Select a payload snapshot, manifest, or debug preview artifact to inspect it.</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No artifacts available until a job is created.</p>
          )}
        </Panel>
      </div>

      <Panel title="History timeline">
        {selectedJob?.history.length ? (
          <div className="space-y-3">
            {selectedJob.history.map((event) => (
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
          <p className="text-sm text-slate-400">Append-only job history will appear here after the first deterministic creation event.</p>
        )}
      </Panel>
    </AppShell>
  );
}
