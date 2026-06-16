import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AcquisitionItemRead,
  type AcquisitionRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { AddBooksFlow } from "../components/acquisitions/AddBooksFlow";
import { CostAllocationPanel } from "../components/acquisitions/CostAllocationPanel";
import { acquisitionSourceLabel } from "../config/acquisitionSources";

export function AcquisitionDetailPage(): JSX.Element {
  const { acquisitionId: idParam } = useParams();
  const acquisitionId = Number(idParam);

  const [acquisition, setAcquisition] = useState<AcquisitionRead | null>(null);
  const [items, setItems] = useState<AcquisitionItemRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddBooks, setShowAddBooks] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [acq, itemsResp] = await Promise.all([
        apiClient.getAcquisition(acquisitionId),
        apiClient.listAcquisitionItems(acquisitionId),
      ]);
      setAcquisition(acq);
      setItems(itemsResp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load acquisition.");
    } finally {
      setLoading(false);
    }
  }, [acquisitionId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const markComplete = useCallback(async () => {
    try {
      await apiClient.completeAcquisition(acquisitionId);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not complete acquisition.");
    }
  }, [acquisitionId, refresh]);

  const removeItem = useCallback(
    async (inventoryCopyId: number) => {
      try {
        await apiClient.deleteAcquisitionItem(acquisitionId, inventoryCopyId);
        await refresh();
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not remove book.");
      }
    },
    [acquisitionId, refresh],
  );

  if (loading) {
    return (
      <AppShell>
        <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-300">Loading…</div>
      </AppShell>
    );
  }

  if (!acquisition) {
    return (
      <AppShell>
        <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-300">
          <p role="alert" className="text-rose-300">
            {error ?? "Acquisition not found."}
          </p>
          <Link to="/acquisitions" className="mt-3 inline-block text-sky-300 hover:underline">
            ← Back to acquisitions
          </Link>
        </div>
      </AppShell>
    );
  }

  const isOpen = acquisition.status === "OPEN";

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto max-w-5xl px-4 py-8">
          <Link to="/acquisitions" className="text-sm text-sky-300 hover:underline">
            ← All acquisitions
          </Link>

          <header className="mt-3 rounded-2xl border border-slate-700 bg-slate-900 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs font-semibold text-sky-300">
                  {acquisitionSourceLabel(acquisition.acquisition_type)}
                </span>
                <h1 className="mt-2 text-2xl font-semibold text-white">
                  {acquisition.seller_name || "Unknown seller"}
                </h1>
                <p className="text-sm text-slate-400">{acquisition.purchase_date || "No purchase date"}</p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-sm font-semibold ${
                  isOpen ? "bg-emerald-500/15 text-emerald-300" : "bg-slate-800 text-slate-400"
                }`}
              >
                {acquisition.status}
              </span>
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Stat label="Total paid" value={`$${acquisition.total_paid}`} />
              <Stat label="Shipping / Tax" value={`$${acquisition.shipping_paid} / $${acquisition.tax_paid}`} />
              <Stat label="Books" value={String(acquisition.item_count)} />
              <Stat label="Avg cost/book" value={`$${acquisition.cost_per_book}`} />
            </dl>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setShowAddBooks((v) => !v)}
                disabled={!isOpen}
                className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
              >
                Add Books
              </button>
              <button
                type="button"
                onClick={markComplete}
                disabled={!isOpen}
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:border-slate-400 disabled:opacity-50"
              >
                Mark Complete
              </button>
            </div>
          </header>

          {error ? (
            <p role="alert" className="mt-4 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">
              {error}
            </p>
          ) : null}

          {showAddBooks && isOpen ? (
            <div className="mt-5">
              <AddBooksFlow
                acquisitionId={acquisitionId}
                onBooksAdded={refresh}
                onClose={() => setShowAddBooks(false)}
              />
            </div>
          ) : null}

          <div className="mt-5">
            <CostAllocationPanel acquisition={acquisition} onAllocated={refresh} />
          </div>

          <section aria-label="Books in this acquisition" className="mt-5">
            <h2 className="text-lg font-semibold text-white">Books ({items.length})</h2>
            {items.length === 0 ? (
              <p className="mt-2 text-sm text-slate-400">No books added yet. Tap “Add Books” to begin.</p>
            ) : (
              <ul className="mt-3 divide-y divide-slate-800 rounded-2xl border border-slate-700 bg-slate-900">
                {items.map((item) => (
                  <li key={item.inventory_copy_id} className="flex items-center gap-3 p-3">
                    {item.cover_image_url ? (
                      <img src={item.cover_image_url} alt="" className="h-14 w-10 rounded object-cover" />
                    ) : (
                      <span className="flex h-14 w-10 items-center justify-center rounded bg-slate-800 text-[10px] text-slate-400">
                        No cover
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/inventory/${item.inventory_copy_id}`}
                        className="block truncate font-semibold text-white hover:text-sky-300"
                      >
                        {item.series || "Unknown series"} #{item.issue_number || "?"}
                      </Link>
                      <span className="text-xs text-slate-400">
                        {item.publisher || "Unknown publisher"} · ${item.cost_basis}
                        {item.variant_status === "UNKNOWN" ? (
                          <span className="ml-2 rounded bg-amber-500/20 px-1 text-amber-300">Needs review</span>
                        ) : null}
                      </span>
                    </div>
                    {isOpen ? (
                      <button
                        type="button"
                        onClick={() => removeItem(item.inventory_copy_id)}
                        className="rounded-lg border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:border-rose-400 hover:text-rose-300"
                      >
                        Remove
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-lg bg-slate-800/60 px-3 py-2">
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd className="font-semibold text-white">{value}</dd>
    </div>
  );
}
