import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AutomationScheduleCreate,
  type AutomationScheduleRead,
  type AutomationTriggerCreate,
  type AutomationTriggerRead,
  type AutomationWorkflowExecutionRead,
  type AutomationWorkflowRead,
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
    case "ACTIVE":
    case "COMPLETED":
    case "PROCESSED":
      return "border-emerald-400/35 bg-emerald-400/10 text-emerald-100";
    case "RUNNING":
      return "border-cyan-400/35 bg-cyan-400/10 text-cyan-100";
    case "FAILED":
    case "BLOCKED":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-amber-400/35 bg-amber-400/10 text-amber-100";
  }
}

export function AutomationWorkflowsPage() {
  const [schedules, setSchedules] = useState<AutomationScheduleRead[]>([]);
  const [triggers, setTriggers] = useState<AutomationTriggerRead[]>([]);
  const [workflows, setWorkflows] = useState<AutomationWorkflowRead[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<AutomationWorkflowRead | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<AutomationWorkflowExecutionRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creatingSchedule, setCreatingSchedule] = useState(false);
  const [creatingTrigger, setCreatingTrigger] = useState(false);
  const [scheduleForm, setScheduleForm] = useState<AutomationScheduleCreate>({
    schedule_name: "Scheduled maintenance",
    schedule_type: "ONE_TIME",
    workflow_key: "maintenance_schedule_workflow",
    next_run_at: new Date(Date.now() + 60_000).toISOString(),
    metadata_json: {},
  });
  const [triggerForm, setTriggerForm] = useState<AutomationTriggerCreate>({
    trigger_type: "MANUAL_TRIGGER",
    source_event_type: "manual",
    workflow_key: "manual_trigger_workflow",
    trigger_payload_json: {},
    metadata_json: {},
  });

  useEffect(() => {
    void refreshWorkflowData();
  }, []);

  async function refreshWorkflowData(selectedId?: number | null): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const [scheduleResponse, triggerResponse, workflowResponse] = await Promise.all([
        apiClient.listAutomationSchedules({ limit: 50, offset: 0 }),
        apiClient.listAutomationTriggers({ limit: 50, offset: 0 }),
        apiClient.listAutomationWorkflows({ limit: 50, offset: 0 }),
      ]);
      setSchedules(scheduleResponse.items);
      setTriggers(triggerResponse.items);
      setWorkflows(workflowResponse.items);
      const nextId = selectedId ?? workflowResponse.items[0]?.id ?? null;
      if (nextId) {
        const detail = await apiClient.getAutomationWorkflow(nextId);
        setSelectedWorkflow(detail);
        setSelectedExecution(detail.latest_execution ?? null);
      } else {
        setSelectedWorkflow(null);
        setSelectedExecution(null);
      }
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load workflow orchestration workspace.");
    } finally {
      setLoading(false);
    }
  }

  async function inspectWorkflow(workflowId: number): Promise<void> {
    setError(null);
    try {
      const detail = await apiClient.getAutomationWorkflow(workflowId);
      setSelectedWorkflow(detail);
      setSelectedExecution(detail.latest_execution ?? null);
    } catch (loadErr) {
      setError(loadErr instanceof ApiError ? loadErr.message : "Unable to load workflow detail.");
    }
  }

  async function submitSchedule(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setCreatingSchedule(true);
    setError(null);
    try {
      await apiClient.createAutomationSchedule(scheduleForm);
      await refreshWorkflowData();
    } catch (submitErr) {
      setError(submitErr instanceof ApiError ? submitErr.message : "Unable to create automation schedule.");
    } finally {
      setCreatingSchedule(false);
    }
  }

  async function submitTrigger(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setCreatingTrigger(true);
    setError(null);
    try {
      await apiClient.createAutomationTrigger(triggerForm);
      await refreshWorkflowData();
    } catch (submitErr) {
      setError(submitErr instanceof ApiError ? submitErr.message : "Unable to create automation trigger.");
    } finally {
      setCreatingTrigger(false);
    }
  }

  const summary = useMemo(() => {
    const failed = workflows.filter((workflow) => workflow.latest_execution?.execution_status === "FAILED").length;
    const blocked = workflows.filter((workflow) => workflow.blocked_step_count > 0 || workflow.latest_execution?.execution_status === "BLOCKED").length;
    const pending = triggers.filter((trigger) => trigger.trigger_status === "PENDING").length;
    return { failed, blocked, pending };
  }, [triggers, workflows]);

  const artifactRefs = useMemo(() => {
    const refs = selectedExecution?.execution_manifest_json?.artifact_refs;
    return Array.isArray(refs) ? refs : [];
  }, [selectedExecution]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="P41-03"
        title="Workflow Scheduling / Trigger Orchestration"
        description="Deterministic replay-safe automation orchestration for schedules, triggers, dependency-aware workflow sequencing, and append-only execution lineage."
        actions={
          <div className="flex gap-2">
            <Link to="/automation-workers" className="rounded-2xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200">
              Worker runtime
            </Link>
            <Link to="/ops#automation-workflow-ops" className="rounded-2xl border border-cyan-400/35 px-4 py-2 text-sm font-semibold text-cyan-100">
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
        <StatCard label="Active workflows" value={String(workflows.length)} />
        <StatCard label="Blocked workflows" value={String(summary.blocked)} />
        <StatCard label="Pending triggers" value={String(summary.pending)} />
        <StatCard label="Failed executions" value={String(summary.failed)} />
        <StatCard label="Scheduled runs" value={String(schedules.filter((row) => row.schedule_status === "ACTIVE").length)} />
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Panel title="Schedule panel">
          <form className="grid gap-3 md:grid-cols-2" onSubmit={(event) => void submitSchedule(event)}>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3 text-sm text-white"
              value={scheduleForm.schedule_name}
              onChange={(event) => setScheduleForm((current) => ({ ...current, schedule_name: event.target.value }))}
              placeholder="Schedule name"
            />
            <select
              className="rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3 text-sm text-white"
              value={scheduleForm.workflow_key ?? "maintenance_schedule_workflow"}
              onChange={(event) => setScheduleForm((current) => ({ ...current, workflow_key: event.target.value }))}
            >
              <option value="maintenance_schedule_workflow">maintenance_schedule_workflow</option>
              <option value="manual_trigger_workflow">manual_trigger_workflow</option>
            </select>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3 text-sm text-white md:col-span-2"
              value={scheduleForm.next_run_at ?? ""}
              onChange={(event) => setScheduleForm((current) => ({ ...current, next_run_at: event.target.value }))}
              placeholder="ISO next run time"
            />
            <button
              type="submit"
              disabled={creatingSchedule}
              className="rounded-2xl border border-cyan-400/35 bg-cyan-400/10 px-4 py-3 text-sm font-semibold text-cyan-100"
            >
              {creatingSchedule ? "Creating…" : "Create schedule"}
            </button>
          </form>
          <div className="mt-4 space-y-3">
            {schedules.length ? (
              schedules.slice(0, 6).map((schedule) => (
                <div key={schedule.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">{schedule.schedule_name}</p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(schedule.schedule_status)}`}>
                      {schedule.schedule_status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{schedule.metadata_json.workflow_key?.toString() ?? "workflow"}</p>
                  <p className="mt-1 text-xs text-slate-500">Next run {formatDateTime(schedule.next_run_at)}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-600">No schedules created yet.</p>
            )}
          </div>
        </Panel>

        <Panel title="Trigger panel">
          <form className="grid gap-3 md:grid-cols-2" onSubmit={(event) => void submitTrigger(event)}>
            <select
              className="rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3 text-sm text-white"
              value={triggerForm.trigger_type}
              onChange={(event) => setTriggerForm((current) => ({ ...current, trigger_type: event.target.value }))}
            >
              <option value="MANUAL_TRIGGER">MANUAL_TRIGGER</option>
              <option value="SCAN_COMPLETED">SCAN_COMPLETED</option>
              <option value="REPLAY_COMPLETED">REPLAY_COMPLETED</option>
              <option value="JOB_FAILED">JOB_FAILED</option>
            </select>
            <select
              className="rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3 text-sm text-white"
              value={triggerForm.workflow_key ?? "manual_trigger_workflow"}
              onChange={(event) => setTriggerForm((current) => ({ ...current, workflow_key: event.target.value }))}
            >
              <option value="manual_trigger_workflow">manual_trigger_workflow</option>
              <option value="blocked_test_workflow">blocked_test_workflow</option>
              <option value="scan_completed_feed_generation">scan_completed_feed_generation</option>
            </select>
            <input
              className="rounded-2xl border border-white/10 bg-slate-950/45 px-4 py-3 text-sm text-white md:col-span-2"
              value={triggerForm.source_event_type}
              onChange={(event) => setTriggerForm((current) => ({ ...current, source_event_type: event.target.value }))}
              placeholder="Source event type"
            />
            <button
              type="submit"
              disabled={creatingTrigger}
              className="rounded-2xl border border-cyan-400/35 bg-cyan-400/10 px-4 py-3 text-sm font-semibold text-cyan-100"
            >
              {creatingTrigger ? "Creating…" : "Create trigger"}
            </button>
          </form>
          <div className="mt-4 space-y-3">
            {triggers.length ? (
              triggers.slice(0, 6).map((trigger) => (
                <div key={trigger.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">{trigger.trigger_type}</p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(trigger.trigger_status)}`}>
                      {trigger.trigger_status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">{trigger.source_event_type}</p>
                  <p className="mt-1 text-xs text-slate-500">Checksum {shortenChecksum(trigger.trigger_checksum)}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-600">No triggers recorded yet.</p>
            )}
          </div>
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Workflow table">
          {loading ? (
            <p className="text-sm text-slate-600">Loading workflow orchestration…</p>
          ) : workflows.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm text-slate-300">
                <thead className="text-xs uppercase tracking-[0.14em] text-slate-500">
                  <tr>
                    <th className="pb-3 pr-4">Workflow</th>
                    <th className="pb-3 pr-4">Status</th>
                    <th className="pb-3 pr-4">Trigger source</th>
                    <th className="pb-3 pr-4">Executions</th>
                    <th className="pb-3">Dependency status</th>
                  </tr>
                </thead>
                <tbody>
                  {workflows.map((workflow) => (
                    <tr
                      key={workflow.id}
                      className="cursor-pointer border-t border-white/5 align-top transition hover:bg-white/5"
                      onClick={() => void inspectWorkflow(workflow.id)}
                    >
                      <td className="py-3 pr-4">
                        <p className="font-medium text-white">{workflow.workflow_name}</p>
                        <p className="text-xs text-slate-500">{workflow.workflow_category}</p>
                      </td>
                      <td className="py-3 pr-4">
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(workflow.workflow_status)}`}>
                          {workflow.workflow_status}
                        </span>
                      </td>
                      <td className="py-3 pr-4">{workflow.pending_trigger_count ? `${workflow.pending_trigger_count} pending` : "event-driven"}</td>
                      <td className="py-3 pr-4">{workflow.latest_execution ? `latest #${workflow.latest_execution.id}` : "—"}</td>
                      <td className="py-3">{workflow.blocked_step_count ? `${workflow.blocked_step_count} blocked` : `${workflow.steps.length} steps ready`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No workflows registered yet" description="Workflows appear once schedules or triggers seed deterministic orchestration definitions." />
          )}
        </Panel>

        <Panel title="Dependency graph panel">
          {selectedWorkflow?.steps.length ? (
            <div className="space-y-3">
              {selectedWorkflow.steps.map((step) => (
                <div key={step.id} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-slate-900">#{step.step_rank} · {step.step_key}</p>
                  <p className="mt-1 text-xs text-slate-400">{step.job_type} · {step.dependency_mode}</p>
                  <p className="mt-1 text-xs text-slate-500">Delay {step.delay_seconds ?? 0}s · Required {step.required_success ? "yes" : "no"}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Select a workflow to inspect its dependency-aware step graph.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Execution timeline">
          {selectedWorkflow?.latest_execution ? (
            <div className="space-y-3">
              {[selectedWorkflow.latest_execution].map((execution) => (
                <button
                  key={execution.id}
                  type="button"
                  onClick={() => setSelectedExecution(execution)}
                  className="w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-sm text-left transition hover:border-cyan-300/40"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-slate-900">Execution #{execution.id}</p>
                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide ${statusTone(execution.execution_status)}`}>
                      {execution.execution_status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">Checksum {shortenChecksum(execution.execution_checksum)}</p>
                  <p className="mt-1 text-xs text-slate-500">Started {formatDateTime(execution.started_at)} · Completed {formatDateTime(execution.completed_at)}</p>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">No executions available yet.</p>
          )}
        </Panel>

        <Panel title="Issues panel">
          {selectedWorkflow?.blocked_step_count ? (
            <div className="rounded-2xl border border-amber-400/25 bg-amber-500/5 p-4 text-sm text-amber-100">
              This workflow currently has {selectedWorkflow.blocked_step_count} blocked step(s). Review the dependency graph and execution manifest for the preserved blocking reason.
            </div>
          ) : (
            <p className="text-sm text-slate-600">No workflow issues are visible for the selected workflow.</p>
          )}
        </Panel>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <Panel title="Artifact panel">
          {artifactRefs.length ? (
            <div className="space-y-3">
              {artifactRefs.map((artifact, index) => (
                <div key={`${artifact.artifact_type?.toString() ?? "artifact"}-${index}`} className="rounded-2xl border border-white/10 bg-slate-950/45 p-3">
                  <p className="text-sm font-semibold text-slate-900">{String(artifact.artifact_type ?? "artifact")}</p>
                  <p className="mt-1 break-all text-xs text-slate-400">{String(artifact.storage_path ?? "—")}</p>
                  <p className="mt-1 text-xs text-slate-500">Checksum {shortenChecksum(String(artifact.artifact_checksum ?? ""))}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-600">Execution artifacts appear here once a workflow run has been selected.</p>
          )}
        </Panel>

        <Panel title="History timeline">
          {selectedExecution ? (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-sm font-semibold text-slate-900">Activation key</p>
              <p className="mt-1 break-all text-xs text-slate-400">{String(selectedExecution.metadata_json.activation_key ?? "—")}</p>
              <p className="mt-3 text-xs text-slate-500">Replay-safe lineage is embedded in the execution manifest and append-only workflow history.</p>
            </div>
          ) : (
            <p className="text-sm text-slate-600">Select an execution to inspect orchestration lineage metadata.</p>
          )}
        </Panel>
      </div>
    </AppShell>
  );
}
