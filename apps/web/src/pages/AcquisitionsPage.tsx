import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AcquisitionListFilters,
  type AcquisitionListItem,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { ACQUISITION_SOURCE_OPTIONS, acquisitionSourceLabel } from "../config/acquisitionSources";

export function AcquisitionsPage(): JSX.Element {
  const [items, setItems] = useState<AcquisitionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<AcquisitionListFilters>({});

  const load = useCallback(async (active: AcquisitionListFilters) => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.listAcquisitions(active);
      setItems(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load acquisitions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(filters);
  }, [filters, load]);

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto max-w-5xl px-4 py-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">P98 · Acquisitions</p>
              <h1 className="mt-2 text-2xl font-semibold text-white">Your Acquisitions</h1>
            </div>
            <Link
              to="/acquisitions/new"
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
            >
              + New Acquisition
            </Link>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <select
              aria-label="Filter by source"
              value={filters.acquisition_type ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, acquisition_type: e.target.value || undefined }))}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            >
              <option value="">All sources</option>
              {ACQUISITION_SOURCE_OPTIONS.map((option) => (
                <option key={option.type} value={option.type}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              aria-label="Filter by status"
              value={filters.status ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value || undefined }))}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            >
              <option value="">All statuses</option>
              <option value="OPEN">Open</option>
              <option value="COMPLETE">Complete</option>
            </select>
            <input
              aria-label="Search seller"
              placeholder="Search seller / notes"
              value={filters.search ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value || undefined }))}
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
            />
          </div>

          {error ? (
            <p role="alert" className="mt-4 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">
              {error}
            </p>
          ) : null}

          {loading ? (
            <p className="mt-6 text-sm text-slate-400">Loading…</p>
          ) : items.length === 0 ? (
            <p className="mt-6 text-sm text-slate-400">
              No acquisitions yet. Create one to start adding books.
            </p>
          ) : (
            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((item) => (
                <Link
                  key={item.id}
                  to={`/acquisitions/${item.id}`}
                  className="rounded-2xl border border-slate-700 bg-slate-900 p-4 transition hover:border-sky-400"
                >
                  <div className="flex items-center justify-between">
                    <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs font-semibold text-sky-300">
                      {acquisitionSourceLabel(item.acquisition_type)}
                    </span>
                    <span
                      className={`text-xs font-semibold ${
                        item.status === "OPEN" ? "text-emerald-300" : "text-slate-400"
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-slate-300">{item.seller_name || "Unknown seller"}</p>
                  <p className="text-xs text-slate-500">{item.purchase_date || "No date"}</p>
                  <dl className="mt-3 grid grid-cols-3 gap-1 text-center text-xs">
                    <div>
                      <dt className="text-slate-500">Paid</dt>
                      <dd className="font-semibold text-white">${item.total_paid}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Books</dt>
                      <dd className="font-semibold text-white">{item.item_count}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-500">Avg/book</dt>
                      <dd className="font-semibold text-white">${item.cost_per_book}</dd>
                    </div>
                  </dl>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
