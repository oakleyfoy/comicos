import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type LunarFeedDashboardRead,
  type LunarFeedImportSummaryRead,
  type LunarSchedulerHistoryRead,
  type LunarSchedulerStatusRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

function formatWhen(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export function LunarFeedPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<LunarFeedDashboardRead | null>(null);
  const [scheduler, setScheduler] = useState<LunarSchedulerStatusRead | null>(null);
  const [history, setHistory] = useState<LunarSchedulerHistoryRead | null>(null);
  const [lastResult, setLastResult] = useState<LunarFeedImportSummaryRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [feedBody, schedulerBody, historyBody] = await Promise.all([
        apiClient.getLunarFeedDashboard(),
        apiClient.getLunarSchedulerStatus(),
        apiClient.getLunarSchedulerHistory(),
      ]);
      setDashboard(feedBody);
      setScheduler(schedulerBody);
      setHistory(historyBody);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load Lunar feed dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function handleDownloadLatest() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const body = await apiClient.downloadLatestLunarCsv();
      setMessage(`Downloaded ${body.file_name} (${body.file_period}).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Download failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleImportLatestRemote() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const body = await apiClient.importLatestLunarCsvRemote();
      setLastResult(body);
      setMessage(`Imported ${body.records_created} records from ${body.file_name}.`);
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Remote import failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload(file: File) {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const body = await apiClient.uploadLunarFeedCsv(file);
      setLastResult(body);
      setMessage(`Uploaded import ${body.status}: ${body.records_created} created.`);
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload import failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRunNow() {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const body = await apiClient.runLunarSchedulerNow();
      setMessage(`Scheduled run ${body.status}${body.file_name ? `: ${body.file_name}` : ""}.`);
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Run now failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleEnable() {
    setBusy(true);
    try {
      setScheduler(await apiClient.enableLunarScheduler());
      setMessage("Daily Lunar scheduler enabled.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Enable failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable() {
    setBusy(true);
    try {
      setScheduler(await apiClient.disableLunarScheduler());
      setMessage("Daily Lunar scheduler disabled.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Disable failed.");
    } finally {
      setBusy(false);
    }
  }

  const credentialOk = dashboard?.credential_status.credential_available ?? scheduler?.credential_available ?? false;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Release connectors"
        title="Lunar Feed"
        description="Automated daily Lunar product imports and release intelligence refresh (P50-04A/B)."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading Lunar feed…</p> : null}

      {dashboard && scheduler ? (
        <div className="space-y-6">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Credential Status</h2>
            <p className="mt-2 text-sm text-slate-300">
              {credentialOk
                ? `Credentials configured${dashboard.credential_status.username_masked ? ` (${dashboard.credential_status.username_masked})` : ""}.`
                : "LUNAR_USERNAME and LUNAR_PASSWORD are not configured on the server."}
            </p>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Scheduler Status</h2>
            <ul className="mt-3 space-y-1 text-sm text-slate-300">
              <li>Enabled: {scheduler.enabled ? "Yes" : "No"}</li>
              <li>
                Schedule: {scheduler.schedule_type} at {scheduler.schedule_time} ({scheduler.timezone})
              </li>
              <li>Next scheduled run: {formatWhen(scheduler.next_run_at)}</li>
              <li>Last successful run: {formatWhen(scheduler.last_success_at)}</li>
              <li>Last failed run: {formatWhen(scheduler.last_failure_at)}</li>
              <li>
                Last imported file:{" "}
                {scheduler.last_imported_file_name
                  ? `${scheduler.last_imported_file_name} (${scheduler.last_imported_file_period})`
                  : "—"}
              </li>
            </ul>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                disabled={busy || !credentialOk}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                onClick={() => void handleRunNow()}
              >
                Run Now
              </button>
              <button
                type="button"
                disabled={busy || scheduler.enabled}
                className="rounded-xl border border-white/20 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                onClick={() => void handleEnable()}
              >
                Enable
              </button>
              <button
                type="button"
                disabled={busy || !scheduler.enabled}
                className="rounded-xl border border-white/20 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                onClick={() => void handleDisable()}
              >
                Disable
              </button>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Remote Import Controls</h2>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                disabled={busy || !credentialOk}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                onClick={() => void handleDownloadLatest()}
              >
                Download Latest Lunar CSV
              </button>
              <button
                type="button"
                disabled={busy || !credentialOk}
                className="rounded-xl border border-white/20 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                onClick={() => void handleImportLatestRemote()}
              >
                Import Latest Lunar CSV
              </button>
            </div>
            <div className="mt-4">
              <label className="text-sm text-slate-600">Upload CSV (manual fallback)</label>
              <input
                type="file"
                accept=".csv,text/csv"
                disabled={busy}
                className="mt-2 block w-full text-sm text-slate-300"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void handleUpload(file);
                }}
              />
            </div>
          </section>

          {history ? (
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">Import History</h2>
              <p className="mt-2 text-sm text-slate-400">
                {history.import_runs} imports · {history.no_change_runs} no-change · {history.failed_runs} failed
              </p>
              <ul className="mt-3 space-y-2 text-sm text-slate-300">
                {history.runs.slice(0, 8).map((run) => (
                  <li key={run.run_uuid} className="rounded-xl border border-white/5 px-3 py-2">
                    <span className="font-medium text-slate-900">{run.status}</span> · {run.trigger_type} ·{" "}
                    {run.file_name ?? "—"} · imported {run.records_imported}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {dashboard.last_run ? (
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">Latest Manual Feed Run</h2>
              <ul className="mt-3 space-y-1 text-sm text-slate-300">
                <li>Status: {dashboard.last_run.status}</li>
                <li>File: {dashboard.last_run.file_name}</li>
                <li>
                  Imported: {dashboard.last_run.records_created} created / {dashboard.last_run.records_updated} updated
                </li>
                <li>Errors: {dashboard.last_run.records_failed}</li>
              </ul>
            </section>
          ) : null}

          {lastResult ? (
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">Last Import Result</h2>
              <p className="mt-2 text-sm text-slate-300">
                {lastResult.status} — {lastResult.records_processed} processed, {lastResult.records_failed} failed
              </p>
            </section>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}
