import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P72GradingQueueEntryRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { NavPageLoadBanner } from "../components/NavPageLoadBanner";
import { StatusBanner } from "../components/StatusBanner";

const STATUS_FILTERS = [
  "",
  "CANDIDATE",
  "READY_TO_SUBMIT",
  "SUBMITTED",
  "AT_CGC",
  "GRADING_COMPLETE",
  "RETURNED",
  "LISTED",
  "SOLD",
] as const;

export function GradingQueuePage(): JSX.Element {
  const [items, setItems] = useState<P72GradingQueueEntryRead[]>([]);
  const [status, setStatus] = useState<string>("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loadStatus, setLoadStatus] = useState<string | undefined>();
  const [loadMessage, setLoadMessage] = useState<string | undefined>();
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await apiClient.getGradingQueuePage({
        status: status || undefined,
        search: search.trim() || undefined,
      });
      setItems(body.items ?? []);
      setLoadStatus(body.status);
      setLoadMessage(body.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load grading queue.");
    } finally {
      setLoading(false);
    }
  }, [status, search]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Grading operations"
        title="Grading Queue"
        description="Filter, search, and track per-book grading status (P72-02)."
      />
      <NavPageLoadBanner status={loadStatus} message={loadMessage} />
      <div className="mb-4 flex flex-wrap gap-3 text-sm">
        <Link className="text-indigo-600 hover:underline" to="/grading-operations">
          Operations dashboard
        </Link>
        <Link className="text-indigo-600 hover:underline" to="/grading-batches">
          Submission batches
        </Link>
      </div>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-sm text-slate-600">
          Status
          <select
            className="ml-2 rounded-lg border border-slate-200 px-2 py-1"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {STATUS_FILTERS.map((s) => (
              <option key={s || "all"} value={s}>
                {s || "All"}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-slate-600">
          Search
          <input
            className="ml-2 rounded-lg border border-slate-200 px-2 py-1"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Title, publisher…"
          />
        </label>
        <button
          type="button"
          className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm text-white"
          onClick={() => void load()}
        >
          Refresh
        </button>
      </div>
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {loading ? <p className="text-sm text-slate-600">Loading queue…</p> : null}
      {!loading && !items.length ? <p className="text-sm text-slate-500">Queue is empty.</p> : null}
      {items.length ? (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Batch</th>
                <th className="px-3 py-2">Grade</th>
                <th className="px-3 py-2">Cert</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium text-slate-900">{row.title}</td>
                  <td className="px-3 py-2">{row.status}</td>
                  <td className="px-3 py-2">{row.p72_grading_batch_id ?? "—"}</td>
                  <td className="px-3 py-2">{row.actual_grade ?? "—"}</td>
                  <td className="px-3 py-2">{row.certification_number ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </AppShell>
  );
}
