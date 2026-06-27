import { useCallback, useEffect, useState } from "react";

import {
  fetchGcdIdentityBackfillJobs,
  fetchGcdIdentityBackfillStatus,
  rollbackGcdIdentityBackfillJob,
  runGcdIdentityBackfillDryRun,
  runGcdIdentityBackfillWriteBatch,
  type GcdIdentityBackfillJob,
  type GcdIdentityBackfillStatus,
} from "../api/gcdIdentityBackfill";
import { AppShell } from "../components/AppShell";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function num(v: unknown): number {
  return typeof v === "number" ? v : Number(v ?? 0);
}

export function GcdIdentityBackfillDashboardPage(): JSX.Element {
  const [status, setStatus] = useState<GcdIdentityBackfillStatus | null>(null);
  const [publisher, setPublisher] = useState("DC");
  const [yearFrom, setYearFrom] = useState(2009);
  const [yearTo, setYearTo] = useState(2026);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [jobs, setJobs] = useState<GcdIdentityBackfillJob[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [writeLimit, setWriteLimit] = useState(1000);
  const [dryRunLimit, setDryRunLimit] = useState(1000);
  const [refreshCache, setRefreshCache] = useState(false);

  const loadJobs = useCallback(async () => {
    const res = await fetchGcdIdentityBackfillJobs(40);
    setJobs(res.jobs);
  }, []);

  useEffect(() => {
    void fetchGcdIdentityBackfillStatus()
      .then((s) => {
        setStatus(s);
        setYearFrom(s.default_year_from);
        setYearTo(s.default_year_to);
        if (s.focus_publishers.length > 0) setPublisher(s.focus_publishers[0]);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load status"));
    void loadJobs().catch(() => undefined);
  }, [loadJobs]);

  const scopeBody = () => ({
    publisher,
    year_from: yearFrom,
    year_to: yearTo,
    refresh_cache: refreshCache,
  });

  const onDryRun = async () => {
    setBusy("dry-run");
    setError(null);
    try {
      const { job } = await runGcdIdentityBackfillDryRun({ ...scopeBody(), limit: dryRunLimit });
      setReport(job.report);
      await loadJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dry-run failed");
    } finally {
      setBusy(null);
    }
  };

  const onWrite = async () => {
    if (!window.confirm(`P103.5 write: up to ${writeLimit} identity links. Continue?`)) return;
    setBusy("write");
    setError(null);
    try {
      const { job } = await runGcdIdentityBackfillWriteBatch({
        ...scopeBody(),
        limit: writeLimit,
        confirm_write: "YES",
      });
      setReport(job.report);
      await loadJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Write failed");
    } finally {
      setBusy(null);
    }
  };

  const onRollback = async (jobId: number) => {
    if (!window.confirm(`Rollback identity backfill job ${jobId}?`)) return;
    setBusy("rollback");
    setError(null);
    try {
      await rollbackGcdIdentityBackfillJob(jobId);
      await loadJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rollback failed");
    } finally {
      setBusy(null);
    }
  };

  const sampleRows = (report?.sample_rows as Record<string, unknown>[] | undefined) ?? [];

  return (
    <AppShell>
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold text-slate-900">GCD Identity Backfill (P103.5)</h1>
        <p className="text-sm text-slate-600">
          Link GCD issue ids and insert missing catalog UPCs for existing ComicVine-only rows. No new catalog issues;
          never overwrites UPCs or learned barcodes.
        </p>
        {error ? <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p> : null}

        <div className="grid gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4 md:grid-cols-4">
          <label className="text-sm">
            Publisher
            <select
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
              value={publisher}
              onChange={(e) => setPublisher(e.target.value)}
            >
              {(status?.focus_publishers ?? ["DC"]).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Year from
            <input
              type="number"
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
              value={yearFrom}
              onChange={(e) => setYearFrom(Number(e.target.value))}
            />
          </label>
          <label className="text-sm">
            Year to
            <input
              type="number"
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
              value={yearTo}
              onChange={(e) => setYearTo(Number(e.target.value))}
            />
          </label>
          <label className="flex items-end gap-2 text-sm">
            <input type="checkbox" checked={refreshCache} onChange={(e) => setRefreshCache(e.target.checked)} />
            Refresh catalog cache
          </label>
        </div>

        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            disabled={!!busy}
            className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            onClick={() => void onDryRun()}
          >
            {busy === "dry-run" ? "Running…" : "Dry-run"}
          </button>
          <label className="flex items-center gap-2 text-sm">
            Dry-run limit
            <input
              type="number"
              className="w-24 rounded border border-slate-300 px-2 py-1"
              value={dryRunLimit}
              onChange={(e) => setDryRunLimit(Number(e.target.value))}
            />
          </label>
          <button
            type="button"
            disabled={!!busy}
            className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            onClick={() => void onWrite()}
          >
            {busy === "write" ? "Writing…" : "Write batch"}
          </button>
          <label className="flex items-center gap-2 text-sm">
            Write limit
            <input
              type="number"
              className="w-24 rounded border border-slate-300 px-2 py-1"
              value={writeLimit}
              onChange={(e) => setWriteLimit(Number(e.target.value))}
            />
          </label>
        </div>

        {report ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Issues scanned" value={num(report.existing_issues_scanned ?? report.scanned)} />
            <StatCard label="Missing GCD ids" value={num(report.missing_gcd_ids)} />
            <StatCard label="Matched GCD ids" value={num(report.matched_gcd_ids ?? report.matched)} />
            <StatCard label="UPCs projected" value={num(report.projected_upc_inserts)} />
            <StatCard label="UPCs inserted" value={num(report.inserted_upcs)} />
            <StatCard label="Ambiguous skipped" value={num(report.ambiguous_skipped)} />
            <StatCard label="Duplicate CV conflicts" value={num(report.duplicate_cv_conflicts)} />
            <StatCard label="Validation failures" value={num(report.validation_failures)} />
          </div>
        ) : null}

        {sampleRows.length > 0 ? (
          <div>
            <h2 className="mb-2 text-lg font-medium">Sample matches</h2>
            <ul className="space-y-1 text-sm text-slate-700">
              {sampleRows.slice(0, 15).map((row, i) => (
                <li key={i}>
                  #{String(row.catalog_issue_id)} {String(row.series)} #{String(row.issue_number)} → GCD{" "}
                  {String(row.gcd_issue_id)}
                  {row.barcode ? ` / ${String(row.barcode)}` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div>
          <h2 className="mb-2 text-lg font-medium">Recent jobs</h2>
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase text-slate-600">
                <tr>
                  <th className="px-3 py-2">ID</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Updated</th>
                  <th className="px-3 py-2">UPCs</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.job_id} className="border-t border-slate-200">
                    <td className="px-3 py-2">{j.job_id}</td>
                    <td className="px-3 py-2">{j.job_type}</td>
                    <td className="px-3 py-2">{j.status}</td>
                    <td className="px-3 py-2">{j.updated_issues}</td>
                    <td className="px-3 py-2">{j.inserted_upcs}</td>
                    <td className="px-3 py-2">
                      {j.status === "completed" && j.job_type.includes("write") ? (
                        <button
                          type="button"
                          className="text-red-700 underline"
                          disabled={!!busy}
                          onClick={() => void onRollback(j.job_id)}
                        >
                          Rollback
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
