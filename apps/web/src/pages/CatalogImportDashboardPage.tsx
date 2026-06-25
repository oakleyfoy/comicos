import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchGcdImportJobs,
  fetchGcdImportMatrix,
  fetchGcdImportScope,
  fetchGcdImportStatus,
  gcdImportScopeCsvUrl,
  rollbackGcdImportJob,
  runGcdImportDryRun,
  runGcdImportWriteBatch,
  type GcdImportCellStats,
  type GcdImportJob,
  type GcdImportStatus,
} from "../api/catalogImport";
import { TOKEN_STORAGE_KEY } from "../api/client";
import { AppShell } from "../components/AppShell";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function cellLabel(cell: GcdImportCellStats | undefined): string {
  if (!cell) return "—";
  return String(cell.clean_candidates);
}

export function CatalogImportDashboardPage(): JSX.Element {
  const [status, setStatus] = useState<GcdImportStatus | null>(null);
  const [yearFrom, setYearFrom] = useState(2009);
  const [yearTo, setYearTo] = useState(2026);
  const [matrixCells, setMatrixCells] = useState<GcdImportCellStats[]>([]);
  const [matrixElapsed, setMatrixElapsed] = useState<number | null>(null);
  const [selectedPublisher, setSelectedPublisher] = useState("DC");
  const [selectedYear, setSelectedYear] = useState(2018);
  const [scopeStats, setScopeStats] = useState<GcdImportCellStats | null>(null);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [jobs, setJobs] = useState<GcdImportJob[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [writeLimit, setWriteLimit] = useState(100);
  const [refreshCache, setRefreshCache] = useState(false);

  const loadJobs = useCallback(async () => {
    const res = await fetchGcdImportJobs(40);
    setJobs(res.jobs);
  }, []);

  useEffect(() => {
    void fetchGcdImportStatus()
      .then((s) => {
        setStatus(s);
        setYearFrom(s.default_year_from);
        setYearTo(s.default_year_to);
        if (s.focus_publishers.length > 0) setSelectedPublisher(s.focus_publishers[0]);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load status"));
    void loadJobs().catch(() => undefined);
  }, [loadJobs]);

  const matrixByKey = useMemo(() => {
    const m = new Map<string, GcdImportCellStats>();
    for (const c of matrixCells) m.set(`${c.publisher}:${c.year}`, c);
    return m;
  }, [matrixCells]);

  const years = useMemo(() => {
    const ys: number[] = [];
    for (let y = yearFrom; y <= yearTo; y += 1) ys.push(y);
    return ys;
  }, [yearFrom, yearTo]);

  const loadScope = useCallback(async () => {
    setBusy("scope");
    setError(null);
    try {
      const res = await fetchGcdImportScope({
        publisher: selectedPublisher,
        year: selectedYear,
        preview_limit: 100,
        refresh_cache: refreshCache,
      });
      setScopeStats(res.stats);
      setPreviewRows(res.preview_rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scope load failed");
    } finally {
      setBusy(null);
    }
  }, [selectedPublisher, selectedYear, refreshCache]);

  const loadMatrix = async () => {
    setBusy("matrix");
    setError(null);
    try {
      const res = await fetchGcdImportMatrix({
        year_from: yearFrom,
        year_to: yearTo,
        refresh_cache: refreshCache,
      });
      setMatrixCells(res.cells);
      setMatrixElapsed(res.elapsed_seconds);
      await loadJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Matrix scan failed");
    } finally {
      setBusy(null);
    }
  };

  const onSelectCell = (publisher: string, year: number) => {
    setSelectedPublisher(publisher);
    setSelectedYear(year);
  };

  useEffect(() => {
    if (status) void loadScope();
  }, [status, selectedPublisher, selectedYear, loadScope]);

  const exportCsv = () => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);
    const url = gcdImportScopeCsvUrl({ publisher: selectedPublisher, year: selectedYear, preview_limit: 100 });
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `gcd_preview_${selectedPublisher}_${selectedYear}.csv`;
        a.click();
      })
      .catch((e) => setError(e instanceof Error ? e.message : "CSV export failed"));
  };

  const onDryRun = async () => {
    setBusy("dry-run");
    setError(null);
    try {
      const { job } = await runGcdImportDryRun({
        publisher: selectedPublisher,
        year: selectedYear,
        preview_limit: 100,
        refresh_cache: refreshCache,
      });
      setScopeStats(job.scope_stats as unknown as GcdImportCellStats);
      const report = job.report as { preview_rows?: Record<string, unknown>[] };
      if (report.preview_rows) setPreviewRows(report.preview_rows);
      await loadJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dry-run failed");
    } finally {
      setBusy(null);
    }
  };

  const onWrite = async () => {
    if (!window.confirm(`Write up to ${writeLimit} clean GCD rows for ${selectedPublisher} ${selectedYear}?`)) return;
    setBusy("write");
    setError(null);
    try {
      await runGcdImportWriteBatch({
        publisher: selectedPublisher,
        year: selectedYear,
        limit: writeLimit,
        confirm_write: "YES",
        refresh_cache: refreshCache,
      });
      await loadJobs();
      await loadScope();
      await loadMatrix().catch(() => undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Write batch failed");
    } finally {
      setBusy(null);
    }
  };

  const publishers = status?.focus_publishers ?? [];

  return (
    <AppShell>
      <div className="mx-auto max-w-7xl px-4 py-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Catalog</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">GCD Import Dashboard</h1>
        <p className="mt-2 max-w-3xl text-slate-600">
          Review publisher/year buckets before every write batch. Dry-run and execute imports with job tracking and
          rollback IDs.
        </p>

        {error ? <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

        {status ? (
          <p className="mt-4 text-sm text-slate-500">
            GCD: {status.gcd_database_exists ? "ready" : "missing"} · Cache:{" "}
            {status.catalog_cache_exists ? "ready" : "will export on refresh"}
          </p>
        ) : null}

        <div className="mt-6 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <label className="text-sm">
            Year from
            <input
              type="number"
              className="ml-2 w-24 rounded border border-slate-300 px-2 py-1"
              value={yearFrom}
              onChange={(e) => setYearFrom(Number(e.target.value))}
            />
          </label>
          <label className="text-sm">
            Year to
            <input
              type="number"
              className="ml-2 w-24 rounded border border-slate-300 px-2 py-1"
              value={yearTo}
              onChange={(e) => setYearTo(Number(e.target.value))}
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={refreshCache} onChange={(e) => setRefreshCache(e.target.checked)} />
            Refresh catalog cache
          </label>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void loadMatrix()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {busy === "matrix" ? "Scanning…" : "Refresh matrix"}
          </button>
          {matrixElapsed != null ? (
            <span className="text-sm text-slate-500">Last matrix scan: {matrixElapsed.toFixed(1)}s</span>
          ) : null}
        </div>

        {matrixCells.length > 0 ? (
          <div className="mt-6 overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-100 text-slate-600">
                <tr>
                  <th className="px-2 py-2">Publisher</th>
                  {years.map((y) => (
                    <th key={y} className="px-2 py-2">
                      {y}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {publishers.map((pub) => (
                  <tr key={pub} className="border-t border-slate-100">
                    <td className="px-2 py-1 font-medium text-slate-800">{pub}</td>
                    {years.map((y) => {
                      const cell = matrixByKey.get(`${pub}:${y}`);
                      const selected = pub === selectedPublisher && y === selectedYear;
                      return (
                        <td key={y} className="px-1 py-1">
                          <button
                            type="button"
                            title={
                              cell
                                ? `clean ${cell.clean_candidates} · existing ${cell.existing_issues} · ~${cell.estimated_write_seconds}s write`
                                : "no rows"
                            }
                            onClick={() => onSelectCell(pub, y)}
                            className={`min-w-[2.5rem] rounded px-1 py-1 ${
                              selected ? "bg-indigo-600 text-white" : "bg-slate-50 text-slate-800 hover:bg-indigo-50"
                            }`}
                          >
                            {cellLabel(cell)}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
              Cell values = clean primary candidates. Click a cell to load scope detail below.
            </p>
          </div>
        ) : null}

        <div className="mt-8 grid gap-4 lg:grid-cols-2">
          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">
              Scope: {selectedPublisher} · {selectedYear}
            </h2>
            {scopeStats ? (
              <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
                <StatCard label="Clean" value={scopeStats.clean_candidates} />
                <StatCard label="Variants" value={scopeStats.variants} />
                <StatCard label="Reprints" value={scopeStats.reprints} />
                <StatCard label="Foreign" value={scopeStats.foreign_editions} />
                <StatCard label="Conflicts" value={scopeStats.conflicts} />
                <StatCard label="Existing" value={scopeStats.existing_issues} />
                <StatCard label="Barcodes" value={scopeStats.barcodes_available} />
                <StatCard label="Est. write (s)" value={scopeStats.estimated_write_seconds} />
                <StatCard label="Est. scan (s)" value={scopeStats.estimated_scan_seconds} />
              </div>
            ) : (
              <p className="mt-4 text-sm text-slate-500">Loading scope…</p>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => void loadScope()}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
              >
                Reload preview
              </button>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => exportCsv()}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
              >
                Export CSV
              </button>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => void onDryRun()}
                className="rounded-lg border border-indigo-300 px-3 py-1.5 text-sm text-indigo-800 hover:bg-indigo-50"
              >
                Dry-run job
              </button>
              <label className="flex items-center gap-2 text-sm">
                Limit
                <input
                  type="number"
                  min={1}
                  max={status?.max_write_batch_limit ?? 100}
                  value={writeLimit}
                  onChange={(e) => setWriteLimit(Number(e.target.value))}
                  className="w-16 rounded border border-slate-300 px-2 py-1"
                />
              </label>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => void onWrite()}
                className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                Execute write batch
              </button>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">Preview (first 100 clean rows)</h2>
            <div className="mt-3 max-h-96 overflow-auto text-xs">
              <table className="min-w-full">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className="py-1 pr-2">Series</th>
                    <th className="py-1 pr-2">#</th>
                    <th className="py-1 pr-2">GCD</th>
                    <th className="py-1">Barcode</th>
                  </tr>
                </thead>
                <tbody>
                  {previewRows.map((row) => (
                    <tr key={String(row.gcd_issue_id)} className="border-t border-slate-100">
                      <td className="py-1 pr-2">{String(row.series ?? "")}</td>
                      <td className="py-1 pr-2">{String(row.issue_number ?? "")}</td>
                      <td className="py-1 pr-2">{String(row.gcd_issue_id ?? "")}</td>
                      <td className="py-1 font-mono">{String(row.barcode ?? "—")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {previewRows.length === 0 ? <p className="text-slate-500">No preview rows yet.</p> : null}
            </div>
          </section>
        </div>

        <section className="mt-8 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Import jobs</h2>
          <div className="mt-3 overflow-x-auto text-sm">
            <table className="min-w-full text-left">
              <thead className="text-slate-500">
                <tr>
                  <th className="py-1 pr-3">Job</th>
                  <th className="py-1 pr-3">Rollback ID</th>
                  <th className="py-1 pr-3">Type</th>
                  <th className="py-1 pr-3">Status</th>
                  <th className="py-1 pr-3">Issues</th>
                  <th className="py-1 pr-3">UPCs</th>
                  <th className="py-1 pr-3">Skipped</th>
                  <th className="py-1 pr-3">Errors</th>
                  <th className="py-1">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id} className="border-t border-slate-100">
                    <td className="py-2 pr-3">{job.job_id}</td>
                    <td className="py-2 pr-3 font-mono">{job.rollback_id}</td>
                    <td className="py-2 pr-3">{job.job_type}</td>
                    <td className="py-2 pr-3">{job.status}</td>
                    <td className="py-2 pr-3">{job.inserted_issues}</td>
                    <td className="py-2 pr-3">{job.inserted_upcs}</td>
                    <td className="py-2 pr-3">{job.skipped}</td>
                    <td className="py-2 pr-3">{job.errors}</td>
                    <td className="py-2">
                      {job.job_type === "gcd_write_batch" && job.status === "completed" ? (
                        <button
                          type="button"
                          className="text-red-700 hover:underline"
                          onClick={() => {
                            if (!window.confirm(`Rollback job ${job.job_id}?`)) return;
                            void rollbackGcdImportJob(job.job_id)
                              .then(() => loadJobs())
                              .catch((e) => setError(e instanceof Error ? e.message : "Rollback failed"));
                          }}
                        >
                          Rollback
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
