import { useCallback, useEffect, useState } from "react";

import {
  fetchGcdEnrichmentJobs,
  fetchGcdEnrichmentStatus,
  rollbackGcdEnrichmentJob,
  runGcdEnrichmentDryRun,
  runGcdEnrichmentWriteBatch,
  type GcdEnrichmentJob,
  type GcdEnrichmentStatus,
} from "../api/gcdEnrichment";
import { AppShell } from "../components/AppShell";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export function GcdEnrichmentDashboardPage(): JSX.Element {
  const [status, setStatus] = useState<GcdEnrichmentStatus | null>(null);
  const [publisher, setPublisher] = useState("DC");
  const [yearFrom, setYearFrom] = useState(2009);
  const [yearTo, setYearTo] = useState(2026);
  const [useSingleYear, setUseSingleYear] = useState(true);
  const [singleYear, setSingleYear] = useState(2018);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [jobs, setJobs] = useState<GcdEnrichmentJob[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [writeLimit, setWriteLimit] = useState(100);
  const [refreshCache, setRefreshCache] = useState(false);

  const loadJobs = useCallback(async () => {
    const res = await fetchGcdEnrichmentJobs(40);
    setJobs(res.jobs);
  }, []);

  useEffect(() => {
    void fetchGcdEnrichmentStatus()
      .then((s) => {
        setStatus(s);
        setYearFrom(s.default_year_from);
        setYearTo(s.default_year_to);
        if (s.focus_publishers.length > 0) setPublisher(s.focus_publishers[0]);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load status"));
    void loadJobs().catch(() => undefined);
  }, [loadJobs]);

  const dryRunBody = () => ({
    publisher,
    year: useSingleYear ? singleYear : undefined,
    year_from: useSingleYear ? undefined : yearFrom,
    year_to: useSingleYear ? undefined : yearTo,
    refresh_cache: refreshCache,
  });

  const onDryRun = async () => {
    setBusy("dry-run");
    setError(null);
    try {
      const { job } = await runGcdEnrichmentDryRun(dryRunBody());
      setReport(job.report);
      await loadJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dry-run failed");
    } finally {
      setBusy(null);
    }
  };

  const onWritePilot = async () => {
    if (!window.confirm(`P103 write: up to ${writeLimit} rows, update-only. Continue?`)) return;
    setBusy("write");
    setError(null);
    try {
      const { job } = await runGcdEnrichmentWriteBatch({
        ...dryRunBody(),
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
    if (!window.confirm(`Rollback enrichment job ${jobId}?`)) return;
    setBusy("rollback");
    setError(null);
    try {
      await rollbackGcdEnrichmentJob(jobId);
      await loadJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rollback failed");
    } finally {
      setBusy(null);
    }
  };

  const sampleUpdates = (report?.sample_updates as Record<string, unknown>[] | undefined) ?? [];
  const conflictSamples = (report?.conflict_samples as Record<string, unknown>[] | undefined) ?? [];

  return (
    <AppShell>
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold text-slate-900">GCD Enrichment (P103)</h1>
        <p className="text-sm text-slate-600">
          Update-only enrichment from GCD: fill missing UPCs, dates, variants, and GCD ids. No new issues. Writes
          capped at {status?.max_write_batch_limit ?? 50_000} rows per job.
        </p>
        {error ? <p className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p> : null}
        {status ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="GCD DB" value={status.gcd_database_exists ? "OK" : "missing"} />
            <StatCard label="Catalog cache" value={status.catalog_cache_exists ? "OK" : "missing"} />
            <StatCard label="Write cap" value={status.max_write_batch_limit} />
            <StatCard label="Publishers" value={status.focus_publishers.length} />
          </div>
        ) : null}

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
          <h2 className="text-lg font-semibold text-slate-900">Scope</h2>
          <div className="flex flex-wrap gap-3 items-end">
            <label className="text-sm">
              Publisher
              <select
                className="mt-1 rounded border border-slate-300 px-2 py-1"
                value={publisher}
                onChange={(e) => setPublisher(e.target.value)}
              >
                {(status?.focus_publishers ?? []).map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="text-sm flex items-center gap-2">
              <input type="checkbox" checked={useSingleYear} onChange={(e) => setUseSingleYear(e.target.checked)} />
              Single year
            </label>
            {useSingleYear ? (
              <label className="text-sm">
                Year
                <input
                  type="number"
                  className="mt-1 rounded border border-slate-300 px-2 py-1 w-24"
                  value={singleYear}
                  onChange={(e) => setSingleYear(Number(e.target.value))}
                />
              </label>
            ) : (
              <>
                <label className="text-sm">
                  From
                  <input
                    type="number"
                    className="mt-1 rounded border border-slate-300 px-2 py-1 w-24"
                    value={yearFrom}
                    onChange={(e) => setYearFrom(Number(e.target.value))}
                  />
                </label>
                <label className="text-sm">
                  To
                  <input
                    type="number"
                    className="mt-1 rounded border border-slate-300 px-2 py-1 w-24"
                    value={yearTo}
                    onChange={(e) => setYearTo(Number(e.target.value))}
                  />
                </label>
              </>
            )}
            <label className="text-sm flex items-center gap-2">
              <input type="checkbox" checked={refreshCache} onChange={(e) => setRefreshCache(e.target.checked)} />
              Refresh cache
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy !== null}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm text-white disabled:opacity-50"
              onClick={() => void onDryRun()}
            >
              {busy === "dry-run" ? "Running dry-run…" : "Run dry-run / impact report"}
            </button>
            <label className="text-sm">
              Pilot limit
              <input
                type="number"
                min={1}
                max={status?.max_write_batch_limit ?? 50000}
                className="ml-2 rounded border border-slate-300 px-2 py-1 w-20"
                value={writeLimit}
                onChange={(e) => setWriteLimit(Number(e.target.value))}
              />
            </label>
            <button
              type="button"
              disabled={busy !== null}
              className="rounded-lg border border-amber-600 px-4 py-2 text-sm text-amber-800 disabled:opacity-50"
              onClick={() => void onWritePilot()}
            >
              {busy === "write" ? "Writing…" : "Run write batch"}
            </button>
          </div>
        </div>

        {report ? (
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
            <h2 className="text-lg font-semibold text-slate-900">Impact report</h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard label="Matched to GCD" value={String(report.matched_to_gcd ?? "—")} />
              <StatCard label="Missing GCD ids" value={String(report.missing_gcd_ids ?? "—")} />
              <StatCard label="Missing UPCs" value={String(report.missing_upc ?? "—")} />
              <StatCard label="Missing dates" value={String(report.missing_dates ?? "—")} />
              <StatCard label="Missing printing" value={String(report.missing_printing ?? "—")} />
              <StatCard label="Missing variants" value={String(report.missing_variants ?? "—")} />
              <StatCard label="Projected updates" value={String(report.projected_field_updates ?? "—")} />
              <StatCard label="Projected UPC inserts" value={String(report.projected_upc_inserts ?? "—")} />
              <StatCard label="Conflicts" value={String(report.conflicts ?? "—")} />
              <StatCard label="Elapsed (s)" value={String(report.elapsed_seconds ?? "—")} />
            </div>
            {sampleUpdates.length > 0 ? (
              <details>
                <summary className="cursor-pointer text-sm font-medium">Sample updates ({sampleUpdates.length})</summary>
                <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-50 p-2 text-xs">
                  {JSON.stringify(sampleUpdates.slice(0, 10), null, 2)}
                </pre>
              </details>
            ) : null}
            {conflictSamples.length > 0 ? (
              <details>
                <summary className="cursor-pointer text-sm font-medium">Conflict samples</summary>
                <pre className="mt-2 max-h-64 overflow-auto rounded bg-slate-50 p-2 text-xs">
                  {JSON.stringify(conflictSamples.slice(0, 10), null, 2)}
                </pre>
              </details>
            ) : null}
          </div>
        ) : null}

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900 mb-3">Recent jobs</h2>
          <ul className="divide-y divide-slate-100 text-sm">
            {jobs.map((j) => (
              <li key={j.job_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span>
                  #{j.job_id} {j.job_type} — {j.status} — updated {j.updated_issues} / upc {j.inserted_upcs}
                </span>
                {j.status === "completed" && j.job_type === "gcd_enrichment_write_batch" ? (
                  <button
                    type="button"
                    className="text-amber-700 underline"
                    onClick={() => void onRollback(j.job_id)}
                  >
                    Rollback
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </AppShell>
  );
}
