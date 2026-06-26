import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AcquisitionItemRead, type AcquisitionRead } from "../../api/client";
import {
  ADD_COMICS_ACQUISITION_STORAGE_KEY,
  AddComicsAcquisitionSelect,
} from "../../components/addComics/AddComicsAcquisitionSelect";
import { AcquisitionTreePickerModal } from "../../components/acquisitions/AcquisitionTreePickerModal";
import { AppShell } from "../../components/AppShell";
import { PageHeader } from "../../components/PageHeader";
import { StatusBanner } from "../../components/StatusBanner";

export function AddComicsManualPage(): JSX.Element {
  const [acquisitionId, setAcquisitionId] = useState<number | null>(null);
  const [acquisition, setAcquisition] = useState<AcquisitionRead | null>(null);
  const [items, setItems] = useState<AcquisitionItemRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const refreshItems = useCallback(async (id: number) => {
    const [acq, itemsResp] = await Promise.all([
      apiClient.getAcquisition(id),
      apiClient.listAcquisitionItems(id),
    ]);
    setAcquisition(acq);
    setItems(itemsResp.items);
  }, []);

  const loadAcquisition = useCallback(
    async (id: number) => {
      setLoading(true);
      setError(null);
      setStatus(null);
      try {
        const acq = await apiClient.getAcquisition(id);
        if (acq.status !== "OPEN") {
          setError("That acquisition is complete. Choose or create an open group to add more books.");
          setAcquisitionId(null);
          setAcquisition(null);
          setItems([]);
          sessionStorage.removeItem(ADD_COMICS_ACQUISITION_STORAGE_KEY);
          return;
        }
        setAcquisitionId(id);
        await refreshItems(id);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Could not load acquisition.");
        setAcquisitionId(null);
        setAcquisition(null);
        setItems([]);
      } finally {
        setLoading(false);
      }
    },
    [refreshItems],
  );

  useEffect(() => {
    const stored = sessionStorage.getItem(ADD_COMICS_ACQUISITION_STORAGE_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }
    const parsed = Number(stored);
    if (!Number.isFinite(parsed)) {
      setLoading(false);
      return;
    }
    void loadAcquisition(parsed);
  }, [loadAcquisition]);

  async function onBookAdded(): Promise<void> {
    if (acquisitionId == null) return;
    setStatus(null);
    try {
      const itemsResp = await apiClient.listAcquisitionItems(acquisitionId);
      setItems(itemsResp.items);
      const acq = await apiClient.getAcquisition(acquisitionId);
      setAcquisition(acq);
      setStatus(
        `Added to collection (${itemsResp.items.length} cop${itemsResp.items.length === 1 ? "y" : "ies"} on this acquisition).`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not refresh books.");
    }
  }

  async function finishSession(): Promise<void> {
    if (acquisitionId == null) return;
    setError(null);
    try {
      await apiClient.completeAcquisition(acquisitionId);
      sessionStorage.removeItem(ADD_COMICS_ACQUISITION_STORAGE_KEY);
      setStatus("Acquisition marked complete. Books are in your inventory — open Portfolio to view them.");
      setAcquisitionId(null);
      setAcquisition(null);
      setItems([]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not complete acquisition.");
    }
  }

  const copyCount = acquisition?.item_count ?? items.length;
  const showCatalogTree = acquisitionId != null && !loading && acquisition?.status === "OPEN";

  return (
    <AppShell>
      <PageHeader
        eyebrow="Add Comics"
        title="Manual Entry"
        description="Choose an acquisition group, then browse the local catalog tree to add publisher, series, issue, and variant. Every copy is tied to that group."
        actions={
          <Link
            to="/catalog-universe"
            className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-white/5"
          >
            Browse full universe
          </Link>
        }
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}
      {status ? (
        <div className="mt-6">
          <StatusBanner tone="success">{status}</StatusBanner>
        </div>
      ) : null}

      <div className="mt-8 space-y-8">
        <AddComicsAcquisitionSelect
          selectedId={acquisitionId}
          disabled={loading}
          onSelect={(id) => void loadAcquisition(id)}
        />

        {loading && acquisitionId != null ? (
          <p className="text-sm text-slate-400">Loading acquisition…</p>
        ) : null}

        {showCatalogTree ? (
          <>
            <AcquisitionTreePickerModal
              embedded
              open
              acquisitionId={acquisitionId}
              onClose={() => undefined}
              onCreated={() => void onBookAdded()}
            />

            <section className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-white">This acquisition</h2>
                  <p className="mt-1 text-sm text-slate-400">
                    {acquisition?.seller_name ?? `Acquisition #${acquisitionId}`} · {copyCount} inventory cop
                    {copyCount === 1 ? "y" : "ies"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link
                    to="/dashboard"
                    className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100"
                  >
                    Open portfolio
                  </Link>
                  <button
                    type="button"
                    onClick={() => void finishSession()}
                    className="rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-400"
                  >
                    Done adding
                  </button>
                  <Link
                    to={`/acquisitions/${acquisitionId}`}
                    className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-white/5"
                  >
                    Acquisition detail
                  </Link>
                </div>
              </div>

              {items.length > 0 ? (
                <ul className="mt-4 divide-y divide-white/5 rounded-xl border border-white/5">
                  {items.slice(0, 12).map((row) => (
                    <li key={row.inventory_copy_id} className="flex gap-3 px-3 py-2 text-sm text-slate-200">
                      {row.cover_image_url ? (
                        <img
                          src={row.cover_image_url}
                          alt=""
                          className="h-14 w-10 shrink-0 rounded object-cover"
                        />
                      ) : (
                        <span className="flex h-14 w-10 shrink-0 items-center justify-center rounded bg-slate-800 text-[10px] text-slate-500">
                          —
                        </span>
                      )}
                      <span className="min-w-0 flex-1">
                        <span className="font-medium">
                          {row.series ?? "Unknown series"} #{row.issue_number ?? "?"}
                        </span>
                        {row.variant_label ? (
                          <span className="text-slate-400"> · {row.variant_label}</span>
                        ) : null}
                        {row.needs_catalog_match ? (
                          <span className="mt-0.5 block text-xs text-amber-300">Needs catalog match</span>
                        ) : null}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-4 text-sm text-slate-500">No books yet — use the tree above to add your first copy.</p>
              )}
            </section>
          </>
        ) : acquisitionId == null && !loading ? (
          <p className="text-sm text-slate-500">
            Select or create an acquisition above to open the catalog tree.
          </p>
        ) : null}
      </div>
    </AppShell>
  );
}
