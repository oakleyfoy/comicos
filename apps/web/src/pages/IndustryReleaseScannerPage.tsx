import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  apiClient,
  type IndustryReleaseCandidateRead,
  type IndustryReleaseScanRunRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function IndustryReleaseScannerPage(): JSX.Element {
  const [runs, setRuns] = useState<IndustryReleaseScanRunRead[]>([]);
  const [candidates, setCandidates] = useState<IndustryReleaseCandidateRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [scanList, candidateList] = await Promise.all([
        apiClient.getIndustryReleaseScans(),
        apiClient.getIndustryReleaseCandidates(),
      ]);
      setRuns(scanList.items);
      setCandidates(candidateList.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load industry release scanner.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRunScan() {
    setRunning(true);
    setMessage(null);
    setError(null);
    try {
      const run = await apiClient.runIndustryReleaseScan();
      setMessage(
        `Scan complete — ${run.candidates_created} new candidate(s) from ${run.releases_scanned} Lunar release(s).`,
      );
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to run industry release scan.");
    } finally {
      setRunning(false);
    }
  }

  const latestRun = runs[0] ?? null;

  return (
    <AppShell>
      <PageHeader
        eyebrow="P59-02"
        title="Industry Release Scanner"
        description="Scan Lunar catalog releases for supported publishers and capture monitoring candidates (no spec scoring or purchase recommendations)."
        actions={
          <button
            type="button"
            disabled={running}
            onClick={() => void onRunScan()}
            className="rounded-full border border-cyan-400/40 bg-cyan-400/15 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-400/25 disabled:opacity-50"
          >
            {running ? "Scanning…" : "Run scan"}
          </button>
        }
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {message ? <StatusBanner tone="success">{message}</StatusBanner> : null}

      {latestRun ? (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Latest scan</p>
            <p className="mt-1 text-lg font-semibold text-white">{latestRun.status}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Lunar releases scanned</p>
            <p className="mt-1 text-2xl font-semibold text-cyan-200">{latestRun.releases_scanned}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Candidates (latest run)</p>
            <p className="mt-1 text-2xl font-semibold text-emerald-300">{latestRun.candidates_total}</p>
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 p-4">
            <p className="text-xs uppercase tracking-wide text-slate-500">Publishers included</p>
            <p className="mt-1 text-2xl font-semibold text-white">{latestRun.publishers_included}</p>
          </div>
        </div>
      ) : null}

      {loading ? (
        <p className="mt-6 text-sm text-slate-400">Loading scanner history…</p>
      ) : (
        <div className="mt-8 grid gap-8 lg:grid-cols-2">
          <section>
            <h2 className="text-sm font-semibold text-white">Scan history</h2>
            <div className="mt-3 overflow-x-auto rounded-2xl border border-white/10">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-white/10 bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Started</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Scanned</th>
                    <th className="px-3 py-2">New</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-4 text-slate-500">
                        No scans yet — run a scan to capture Lunar releases.
                      </td>
                    </tr>
                  ) : (
                    runs.map((run) => (
                      <tr key={run.id} className="border-b border-white/5">
                        <td className="px-3 py-2 text-slate-300">{new Date(run.started_at).toLocaleString()}</td>
                        <td className="px-3 py-2">{run.status}</td>
                        <td className="px-3 py-2 text-slate-400">{run.releases_scanned}</td>
                        <td className="px-3 py-2 text-emerald-300">{run.candidates_created}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-white">Monitoring candidates</h2>
            <p className="mt-1 text-xs text-slate-500">From the latest successful scan.</p>
            <div className="mt-3 overflow-x-auto rounded-2xl border border-white/10">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-white/10 bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Publisher</th>
                    <th className="px-3 py-2">Series</th>
                    <th className="px-3 py-2">Issue</th>
                    <th className="px-3 py-2">FOC</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-4 text-slate-500">
                        No candidates yet.
                      </td>
                    </tr>
                  ) : (
                    candidates.map((row) => (
                      <tr key={row.id} className="border-b border-white/5">
                        <td className="px-3 py-2 text-slate-300">{row.publisher_name}</td>
                        <td className="px-3 py-2 text-white">{row.series_name}</td>
                        <td className="px-3 py-2 text-slate-400">#{row.issue_number}</td>
                        <td className="px-3 py-2 text-slate-400">{row.foc_date ?? "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </AppShell>
  );
}
