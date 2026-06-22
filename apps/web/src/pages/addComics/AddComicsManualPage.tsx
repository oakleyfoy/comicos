import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AcquisitionItemRead, type AcquisitionRead } from "../../api/client";
import { AcquisitionTreePickerModal } from "../../components/acquisitions/AcquisitionTreePickerModal";
import { AppShell } from "../../components/AppShell";
import { PageHeader } from "../../components/PageHeader";
import { StatusBanner } from "../../components/StatusBanner";

const MANUAL_ENTRY_STORAGE_KEY = "comicos-manual-entry-acquisition-id";

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

  useEffect(() => {
    let cancelled = false;
    async function bootstrap(): Promise<void> {
      setLoading(true);
      setError(null);
      try {
        const stored = sessionStorage.getItem(MANUAL_ENTRY_STORAGE_KEY);
        if (stored) {
          const parsed = Number(stored);
          if (Number.isFinite(parsed)) {
            try {
              const acq = await apiClient.getAcquisition(parsed);
              if (acq.status === "OPEN") {
                if (cancelled) return;
                setAcquisitionId(parsed);
                await refreshItems(parsed);
                return;
              }
            } catch {
              sessionStorage.removeItem(MANUAL_ENTRY_STORAGE_KEY);
            }
          }
        }
        const created = await apiClient.createAcquisition({
          acquisition_type: "UNKNOWN",
          total_paid: "0",
          shipping_paid: "0",
          tax_paid: "0",
          notes: "Manual catalog entry (Add Comics)",
        });
        sessionStorage.setItem(MANUAL_ENTRY_STORAGE_KEY, String(created.id));
        if (cancelled) return;
        setAcquisitionId(created.id);
        await refreshItems(created.id);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not start manual entry session.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [refreshItems]);

  async function onBookAdded(): Promise<void> {
    if (acquisitionId == null) return;
    setStatus(null);
    try {
      const itemsResp = await apiClient.listAcquisitionItems(acquisitionId);
      setItems(itemsResp.items);
      const acq = await apiClient.getAcquisition(acquisitionId);
      setAcquisition(acq);
      setStatus(`Added to collection (${itemsResp.items.length} cop${itemsResp.items.length === 1 ? "y" : "ies"} this session).`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not refresh books.");
    }
  }

  async function finishSession(): Promise<void> {
    if (acquisitionId == null) return;
    setError(null);
    try {
      await apiClient.completeAcquisition(acquisitionId);
      sessionStorage.removeItem(MANUAL_ENTRY_STORAGE_KEY);
      setStatus("Session complete. Books are in your inventory — open Portfolio to view them.");
      await refreshItems(acquisitionId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not complete session.");
    }
  }

  const copyCount = acquisition?.item_count ?? items.length;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Add Comics"
        title="Manual Entry"
        description="Browse the local catalog tree: pick publisher, series volume, issue number, and cover variant. Books are added to your collection through a lightweight manual session."
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

      {loading || acquisitionId == null ? (
        <p className="mt-8 text-sm text-slate-400">Preparing manual entry…</p>
      ) : (
        <div className="mt-8 space-y-8">
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
                <h2 className="text-lg font-semibold text-white">This session</h2>
                <p className="mt-1 text-sm text-slate-400">
                  {copyCount} inventory cop{copyCount === 1 ? "y" : "ies"} added
                  {acquisition?.status === "COMPLETE" ? " · complete" : " · open"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  to="/dashboard"
                  className="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100"
                >
                  Open portfolio
                </Link>
                {acquisition?.status === "OPEN" ? (
                  <button
                    type="button"
                    onClick={() => void finishSession()}
                    className="rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-400"
                  >
                    Done adding
                  </button>
                ) : null}
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
        </div>
      )}
    </AppShell>
  );
}
