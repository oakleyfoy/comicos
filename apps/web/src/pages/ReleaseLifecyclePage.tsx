import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type P86ReleaseLifecycleDashboardRead,
  type P86ReleaseLifecycleRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function RunTable({ rows, onRetry }: { rows: P86ReleaseLifecycleRunRead[]; onRetry?: (id: number) => void }) {
  if (!rows.length) {
    return <p className="text-sm text-slate-600">None</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm text-slate-700">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
            <th className="py-2 pr-4">Release date</th>
            <th className="py-2 pr-4">Stage</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2 pr-4">Issues</th>
            <th className="py-2 pr-4">Variants</th>
            <th className="py-2 pr-4">Runtime (s)</th>
            <th className="py-2 pr-4">Warnings</th>
            <th className="py-2 pr-4">Failures</th>
            {onRetry ? <th className="py-2">Action</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-slate-100">
              <td className="py-2 pr-4">{r.target_release_date}</td>
              <td className="py-2 pr-4">{r.lifecycle_stage}</td>
              <td className="py-2 pr-4">{r.status}</td>
              <td className="py-2 pr-4">{r.issue_count ?? "—"}</td>
              <td className="py-2 pr-4">{r.variant_count ?? "—"}</td>
              <td className="py-2 pr-4">{r.elapsed_seconds ?? "—"}</td>
              <td className="py-2 pr-4 max-w-xs truncate">{r.warnings?.length ? r.warnings.join("; ") : "—"}</td>
              <td className="py-2 pr-4 max-w-xs truncate">{r.failures?.length ? r.failures.join("; ") : "—"}</td>
              {onRetry ? (
                <td className="py-2">
                  {(r.status === "BLOCKED" || r.status === "FAILED") && (
                    <button
                      type="button"
                      className="rounded-md border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
                      onClick={() => onRetry(r.id)}
                    >
                      Retry
                    </button>
                  )}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ReleaseLifecyclePage(): JSX.Element {
  const [dashboard, setDashboard] = useState<P86ReleaseLifecycleDashboardRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.getReleaseLifecycleDashboard();
      setDashboard(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load release lifecycle dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleRunWeekly() {
    setActionMessage(null);
    try {
      const result = await apiClient.runReleaseLifecycleWeekly();
      setActionMessage(result.message || `Started ${result.runs.length} capture(s).`);
      await load();
    } catch (err) {
      setActionMessage(err instanceof ApiError ? err.message : "Weekly run failed.");
    }
  }

  async function handleRetry(runId: number) {
    setActionMessage(null);
    try {
      await apiClient.retryReleaseLifecycleRun(runId);
      setActionMessage(`Retry started for run ${runId}.`);
      await load();
    } catch (err) {
      setActionMessage(err instanceof ApiError ? err.message : "Retry failed.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Release operations"
        title="Release Lifecycle"
        description="P86 automated LoCG capture at discovery, pre-order, release-day, and post-release cleanup windows."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {actionMessage ? <StatusBanner tone="info">{actionMessage}</StatusBanner> : null}
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          className="rounded-lg bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
          onClick={() => void handleRunWeekly()}
        >
          Run weekly plan
        </button>
        <button
          type="button"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50"
          onClick={() => void load()}
        >
          Refresh
        </button>
      </div>
      {loading ? <p className="text-sm text-slate-600">Loading…</p> : null}
      {dashboard ? (
        <div className="space-y-10">
          {!dashboard.automation.has_completed_weekly_run ? (
            <StatusBanner tone="warning">{dashboard.automation.cron_setup_hint}</StatusBanner>
          ) : null}

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Automation status</h2>
            <p className="mt-2 text-sm text-slate-700">
              Last report:{" "}
              {dashboard.automation.last_report_at
                ? `${new Date(dashboard.automation.last_report_at).toLocaleString()} (${dashboard.automation.last_report_status ?? "—"})`
                : "—"}
            </p>
            <p className="mt-1 text-xs text-slate-500">{dashboard.automation.cron_setup_hint}</p>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Latest weekly report</h2>
            {dashboard.latest_report.status === "EMPTY" ? (
              <p className="mt-2 text-sm text-slate-600">
                No weekly lifecycle report yet. Configure Render Cron or use Run weekly plan.
              </p>
            ) : (
              <div className="mt-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-medium text-slate-900">{dashboard.latest_report.title}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {dashboard.latest_report.created_at
                    ? new Date(dashboard.latest_report.created_at).toLocaleString()
                    : ""}{" "}
                  · {dashboard.latest_report.status}
                </p>
                <pre className="mt-3 whitespace-pre-wrap text-xs text-slate-700">{dashboard.latest_report.body}</pre>
              </div>
            )}
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">This week&apos;s lifecycle plan</h2>
            <p className="mt-1 text-xs text-slate-500">
              Anchor Wednesday {dashboard.anchor_release_date} · batch run date {dashboard.run_date}
              {dashboard.active_running_count > 0 ? ` · ${dashboard.active_running_count} running` : ""}
            </p>
            <div className="mt-3">
              <RunTable
                rows={dashboard.this_week_plan.map((item, idx) => ({
                  id: item.run_id ?? idx,
                  owner_id: 0,
                  run_date: dashboard.run_date,
                  anchor_release_date: dashboard.anchor_release_date,
                  target_release_date: item.target_release_date,
                  lifecycle_stage: item.lifecycle_stage,
                  command: "",
                  status: item.status ?? "NOT_STARTED",
                  started_at: null,
                  completed_at: null,
                  elapsed_seconds: item.elapsed_seconds ?? null,
                  parent_queue_count: null,
                  parent_captured_count: null,
                  issue_count: item.issue_count ?? null,
                  variant_count: item.variant_count ?? null,
                  warnings: item.warnings ?? [],
                  failures: item.failures ?? [],
                  raw_path: "",
                  crosswalk_skipped: true,
                  created_at: "",
                  updated_at: "",
                }))}
              />
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Recent runs</h2>
            <div className="mt-3">
              <RunTable rows={dashboard.recent_runs} onRetry={(id) => void handleRetry(id)} />
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Failed / blocked runs</h2>
            <div className="mt-3">
              <RunTable rows={dashboard.failed_or_blocked} onRetry={(id) => void handleRetry(id)} />
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Upcoming lifecycle dates</h2>
            <ul className="mt-2 space-y-1 text-sm text-slate-700">
              {dashboard.upcoming_lifecycle_dates.map((item) => (
                <li key={`${item.target_release_date}-${item.lifecycle_stage}`}>
                  {item.target_release_date} · {item.lifecycle_stage}
                </li>
              ))}
            </ul>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-slate-900">Latest successful captures</h2>
            <div className="mt-3">
              <RunTable rows={dashboard.latest_successful} />
            </div>
          </section>
        </div>
      ) : null}
    </AppShell>
  );
}
