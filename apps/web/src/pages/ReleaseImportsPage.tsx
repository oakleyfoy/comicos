import { useCallback, useEffect, useState, type ReactNode } from "react";

import { ApiError, apiClient, type ReleaseImportDashboardRead, type ReleaseImportErrorRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

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

export function ReleaseImportsPage(): JSX.Element {
  const [dashboard, setDashboard] = useState<ReleaseImportDashboardRead | null>(null);
  const [errors, setErrors] = useState<ReleaseImportErrorRead[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dash, errBody] = await Promise.all([
        apiClient.getReleaseImportDashboard(),
        apiClient.getReleaseImportErrors({ limit: 20 }),
      ]);
      setDashboard(dash);
      setErrors(errBody.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load release import dashboard.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  async function handleJsonUpload(file: File) {
    setUploading(true);
    setMessage(null);
    setError(null);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as unknown;
      const feed = typeof parsed === "object" && parsed !== null && "series" in parsed ? parsed : { series: [] };
      const run = await apiClient.uploadReleaseImportJson({ file_name: file.name, feed });
      setMessage(`JSON import ${run.status}: ${run.records_created} created, ${run.records_updated} updated.`);
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "JSON upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleCsvUpload(file: File) {
    setUploading(true);
    setMessage(null);
    setError(null);
    try {
      const run = await apiClient.uploadReleaseImportCsv(file);
      setMessage(`CSV import ${run.status}: ${run.records_created} created, ${run.records_updated} updated.`);
      await reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "CSV upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Release data"
        title="Release Imports"
        description="Upload JSON or CSV release feeds, track import history and errors — no live distributor connectors (P50-05)."
      />

      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading import dashboard…</p> : null}

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Panel title="Upload JSON">
          <input
            type="file"
            accept="application/json,.json"
            disabled={uploading}
            className="block w-full text-sm text-slate-300"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void handleJsonUpload(file);
            }}
          />
        </Panel>
        <Panel title="Upload CSV">
          <input
            type="file"
            accept=".csv,text/csv"
            disabled={uploading}
            className="block w-full text-sm text-slate-300"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void handleCsvUpload(file);
            }}
          />
        </Panel>
      </div>

      {dashboard ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard label="Import Success Rate" value={`${(dashboard.import_success_rate * 100).toFixed(1)}%`} />
            <StatCard label="Import Failures" value={String(dashboard.import_failures)} />
            <StatCard label="Recent Imports" value={String(dashboard.recent_imports.length)} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title="Recent Imports">
              {!dashboard.recent_imports.length ? (
                <p className="text-sm text-slate-500">No imports yet.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.recent_imports.map((row) => (
                    <li key={row.id} className="flex justify-between gap-2">
                      <span>
                        {row.file_name} ({row.import_type})
                      </span>
                      <span className="text-slate-400">{row.status}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Import Results">
              {!dashboard.recent_imports.length ? (
                <p className="text-sm text-slate-500">Upload a feed to see results.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.recent_imports.slice(0, 5).map((row) => (
                    <li key={row.id}>
                      {row.records_processed} processed · {row.records_created} created · {row.records_updated} updated ·{" "}
                      {row.records_failed} failed
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Latest Uploads">
              {!dashboard.latest_uploads.length ? (
                <p className="text-sm text-slate-500">No files recorded.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {dashboard.latest_uploads.map((row) => (
                    <li key={row.id}>
                      {row.file_name} ({row.file_type}, {row.file_size} bytes)
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="Import Errors">
              {!errors.length ? (
                <p className="text-sm text-slate-500">No import errors.</p>
              ) : (
                <ul className="space-y-2 text-sm text-slate-300">
                  {errors.map((row) => (
                    <li key={row.id}>
                      <span className="text-slate-400">{row.error_code}</span> — {row.error_message}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
