import { useCallback, useEffect, useState } from "react";

import {
  fetchCoverHydrationStatus,
  runCoverHydrationDryRun,
  runCoverHydrationBatch,
  type CoverHydrationStatus,
} from "../api/coverHydration";
import { AppShell } from "../components/AppShell";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export function CoverHydrationDashboardPage(): JSX.Element {
  const [status, setStatus] = useState<CoverHydrationStatus | null>(null);
  const [pilotLimit, setPilotLimit] = useState(100);
  const [syncLimitDryRun, setSyncLimitDryRun] = useState(0);
  const [runLimit, setRunLimit] = useState(100);
  const [syncLimitRun, setSyncLimitRun] = useState(0);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    const s = await fetchCoverHydrationStatus();
    setStatus(s);
  }, []);

  useEffect(() => {
    void loadStatus().catch((e) => setError(e instanceof Error ? e.message : "Failed to load status"));
  }, [loadStatus]);

  const onDryRun = async () => {
    setBusy("dry-run");
    setError(null);
    try {
      const res = await runCoverHydrationDryRun(pilotLimit, syncLimitDryRun);
      setReport(res.report);
      await loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Dry-run failed");
    } finally {
      setBusy(null);
    }
  };

  const onRun = async () => {
    if (!window.confirm(`Download and fingerprint up to ${runLimit} covers?`)) return;
    setBusy("run");
    setError(null);
    try {
      const res = await runCoverHydrationBatch(runLimit, syncLimitRun);
      setReport(res.summary);
      await loadStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-6 p-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Cover Hydration (P104)</h1>
          <p className="mt-1 text-sm text-slate-600">
            Download catalog covers, generate scanner fingerprints, and cache thumbnails. ComicVine is only used when a
            cover URL is already on the catalog issue metadata.
          </p>
        </div>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        {status ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Catalog issues" value={status.total_catalog_issues} />
            <StatCard label="Eligible (image URL)" value={status.eligible_catalog_issues} />
            <StatCard label="Asset rows" value={status.asset_rows} />
            <StatCard label="Queue coverage %" value={status.queue_coverage_pct} />
            <StatCard label="URL not queued" value={status.eligible_with_url_not_queued} />
            <StatCard label="No asset row" value={status.eligible_without_asset_row} />
            <StatCard label="Pending" value={status.pending} />
            <StatCard label="Complete" value={status.complete} />
            <StatCard label="Failed" value={status.failed} />
            <StatCard label="Skipped no URL" value={status.skipped_no_url} />
            <StatCard label="Rate / hour" value={status.rate_per_hour} />
            <StatCard label="ETA (hours)" value={status.eta_hours ?? "—"} />
            <StatCard label="Downloads / min" value={status.downloads_per_minute} />
          </div>
        ) : null}

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-4">
          <h2 className="text-lg font-medium text-slate-900">Pilot</h2>
          <div className="flex flex-wrap items-end gap-4">
            <label className="text-sm text-slate-700">
              Dry-run limit
              <input
                type="number"
                className="ml-2 rounded border border-slate-300 px-2 py-1"
                value={pilotLimit}
                onChange={(e) => setPilotLimit(Number(e.target.value))}
                min={1}
                max={5000}
              />
            </label>
            <label className="text-sm text-slate-700">
              Sync limit (dry-run)
              <input
                type="number"
                className="ml-2 rounded border border-slate-300 px-2 py-1"
                value={syncLimitDryRun}
                onChange={(e) => setSyncLimitDryRun(Number(e.target.value))}
                min={0}
                max={500000}
              />
            </label>
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void onDryRun()}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy === "dry-run" ? "Running…" : "Dry-run"}
            </button>
            <label className="text-sm text-slate-700">
              Run limit
              <input
                type="number"
                className="ml-2 rounded border border-slate-300 px-2 py-1"
                value={runLimit}
                onChange={(e) => setRunLimit(Number(e.target.value))}
                min={1}
                max={10000}
              />
            </label>
            <label className="text-sm text-slate-700">
              Sync limit (run)
              <input
                type="number"
                className="ml-2 rounded border border-slate-300 px-2 py-1"
                value={syncLimitRun}
                onChange={(e) => setSyncLimitRun(Number(e.target.value))}
                min={0}
                max={500000}
              />
            </label>
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => void onRun()}
              className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy === "run" ? "Running…" : "Run batch"}
            </button>
          </div>
        </div>

        {report ? (
          <pre className="overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-800">
            {JSON.stringify(report, null, 2)}
          </pre>
        ) : null}
      </div>
    </AppShell>
  );
}
