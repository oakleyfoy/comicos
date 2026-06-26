import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AcquisitionItemRead,
  type AcquisitionRead,
} from "../api/client";
import { AppShell } from "../components/AppShell";
import { AddBooksFlow } from "../components/acquisitions/AddBooksFlow";
import { AcquisitionTreePickerModal } from "../components/acquisitions/AcquisitionTreePickerModal";
import { CostAllocationPanel } from "../components/acquisitions/CostAllocationPanel";
import { acquisitionSourceLabel } from "../config/acquisitionSources";

export function AcquisitionDetailPage(): JSX.Element {
  const { acquisitionId: idParam } = useParams();
  const navigate = useNavigate();
  const acquisitionId = Number(idParam);

  const [acquisition, setAcquisition] = useState<AcquisitionRead | null>(null);
  const [items, setItems] = useState<AcquisitionItemRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddBooks, setShowAddBooks] = useState(false);
  const [showTreePicker, setShowTreePicker] = useState(false);

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

  const deleteAcquisition = useCallback(async () => {
    if (!acquisition) return;
    const bookCount = acquisition.item_count;
    const message =
      bookCount > 0
        ? `Delete this acquisition and its ${bookCount} book(s)? This cannot be undone.`
        : "Delete this acquisition? This cannot be undone.";
    if (!window.confirm(message)) return;
    try {
      await apiClient.deleteAcquisition(acquisitionId, bookCount > 0);
      navigate("/acquisitions");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete acquisition.");
    }
  }, [acquisition, acquisitionId, navigate]);

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
        <div className="px-4 py-8 text-slate-600">Loading…</div>
      </AppShell>
    );
  }

  if (!acquisition) {
    return (
      <AppShell>
        <div className="px-4 py-8">
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error ?? "Acquisition not found."}
          </p>
          <Link to="/acquisitions" className="mt-3 inline-block text-sm text-patriot-blue hover:underline">
            ← Back to acquisitions
          </Link>
        </div>
      </AppShell>
    );
  }

  const isOpen = acquisition.status === "OPEN";

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
          <Link to="/acquisitions" className="text-sm text-patriot-blue hover:underline">
            ← All acquisitions
          </Link>

          <header className="mt-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-patriot-blue">
                  {acquisitionSourceLabel(acquisition.acquisition_type)}
                </span>
                <h1 className="mt-2 text-2xl font-semibold text-patriot-navy">
                  {acquisition.seller_name || "Unknown seller"}
                </h1>
                <p className="text-sm text-slate-500">{acquisition.purchase_date || "No purchase date"}</p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-sm font-semibold ${
                  isOpen ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"
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
                className="rounded-lg bg-patriot-blue px-4 py-2 text-sm font-semibold text-white hover:bg-blue-900 disabled:opacity-50"
              >
                Add Books
              </button>
              <button
                type="button"
                onClick={() => setShowTreePicker(true)}
                disabled={!isOpen}
                className="rounded-lg border border-emerald-600 bg-white px-4 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-50 disabled:opacity-50"
              >
                Universe Tree Picker
              </button>
              <button
                type="button"
                onClick={markComplete}
                disabled={!isOpen}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Mark Complete
              </button>
              <button
                type="button"
                onClick={deleteAcquisition}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-red-400 hover:bg-red-50 hover:text-red-800"
              >
                Delete
              </button>
            </div>
          </header>

          {error ? (
            <p
              role="alert"
              className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
            >
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
            <h2 className="text-lg font-semibold text-patriot-navy">Books ({items.length})</h2>
            {items.length === 0 ? (
              <p className="mt-2 text-sm text-slate-600">No books added yet. Tap “Add Books” to begin.</p>
            ) : (
              <ul className="mt-3 divide-y divide-slate-200 rounded-2xl border border-slate-200 bg-white shadow-sm">
                {items.map((item) => (
                  <li key={item.inventory_copy_id} className="flex items-center gap-3 p-3">
                    {item.cover_image_url ? (
                      <img src={item.cover_image_url} alt="" className="h-14 w-10 rounded object-cover" />
                    ) : (
                      <span className="flex h-14 w-10 items-center justify-center rounded bg-slate-100 text-[10px] text-slate-500">
                        No cover
                      </span>
                    )}
                    <div className="min-w-0 flex-1">
                      <Link
                        to={`/inventory/${item.inventory_copy_id}`}
                        className="block truncate font-semibold text-patriot-navy hover:text-patriot-blue"
                      >
                        {item.series || "Unknown series"} #{item.issue_number || "?"}
                        {item.variant_label ? (
                          <span className="ml-1 text-slate-500">({item.variant_label})</span>
                        ) : null}
                      </Link>
                      <span className="text-xs text-slate-600">
                        {item.publisher || "Unknown publisher"} · ${item.cost_basis}
                        {item.is_placeholder ? (
                          <>
                            <span className="ml-2 rounded bg-amber-100 px-1 text-amber-900">Placeholder</span>
                            {item.is_tree_linked ? (
                              <span className="ml-1 rounded bg-emerald-100 px-1 text-emerald-900">Tree Linked</span>
                            ) : null}
                            {item.needs_catalog_match ? (
                              <span className="ml-1 rounded bg-red-100 px-1 text-red-800">
                                Needs Catalog Match
                              </span>
                            ) : null}
                          </>
                        ) : item.variant_status === "UNKNOWN" ? (
                          <span className="ml-2 rounded bg-amber-100 px-1 text-amber-900">Needs review</span>
                        ) : null}
                      </span>
                    </div>
                    {isOpen ? (
                      <button
                        type="button"
                        onClick={() => removeItem(item.inventory_copy_id)}
                        className="rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:border-red-400 hover:bg-red-50 hover:text-red-800"
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

      <AcquisitionTreePickerModal
        acquisitionId={acquisitionId}
        open={showTreePicker}
        onClose={() => setShowTreePicker(false)}
        onCreated={() => void refresh()}
      />
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-semibold text-patriot-navy">{value}</dd>
    </div>
  );
}
