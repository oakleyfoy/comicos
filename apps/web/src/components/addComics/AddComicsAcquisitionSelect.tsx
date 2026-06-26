import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type AcquisitionListItem,
  type AcquisitionRead,
} from "../../api/client";

export const ADD_COMICS_ACQUISITION_STORAGE_KEY = "comicos.addComics.acquisitionId";

function formatAcquisitionOption(item: AcquisitionListItem): string {
  const label =
    item.seller_name?.trim() ||
    `Acquisition #${item.id}`;
  const date = item.purchase_date ? ` · ${item.purchase_date}` : "";
  const count = item.item_count > 0 ? ` · ${item.item_count} books` : "";
  return `${label}${date}${count}`;
}

type Props = {
  selectedId: number | null;
  onSelect: (id: number, row: AcquisitionRead | AcquisitionListItem) => void;
  disabled?: boolean;
};

export function AddComicsAcquisitionSelect({ selectedId, onSelect, disabled }: Props): JSX.Element {
  const [items, setItems] = useState<AcquisitionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newLabel, setNewLabel] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiClient.listAcquisitions({ status: "OPEN" });
      setItems(resp.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load acquisitions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreateQuick(): Promise<void> {
    const label = newLabel.trim();
    if (!label) return;
    setCreating(true);
    setError(null);
    try {
      const created = await apiClient.createAcquisition({
        acquisition_type: "OTHER",
        seller_name: label,
        total_paid: "0",
        shipping_paid: "0",
        tax_paid: "0",
        notes: "Bulk scan / photo intake",
      });
      sessionStorage.setItem(ADD_COMICS_ACQUISITION_STORAGE_KEY, String(created.id));
      onSelect(created.id, created);
      setNewLabel("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create acquisition.");
    } finally {
      setCreating(false);
    }
  }

  function onChangeSelect(value: string): void {
    const id = Number(value);
    if (!Number.isFinite(id)) return;
    const row = items.find((i) => i.id === id);
    if (!row) return;
    sessionStorage.setItem(ADD_COMICS_ACQUISITION_STORAGE_KEY, String(id));
    onSelect(id, row);
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.15em] text-slate-500">Acquisition group</p>
          <p className="mt-1 text-sm text-slate-600">
            Every book added in this session is tied to one open acquisition. Retailer orders create their own
            automatically.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Link to="/acquisitions" className="font-medium text-blue-700 hover:underline">
            All acquisitions
          </Link>
          <Link to="/acquisitions/new" className="font-medium text-blue-700 hover:underline">
            Full wizard
          </Link>
        </div>
      </div>

      {error ? (
        <p role="alert" className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {error}
        </p>
      ) : null}

      <label className="mt-4 block text-xs font-semibold uppercase text-slate-500">Open acquisition</label>
      <select
        aria-label="Select acquisition"
        disabled={disabled || loading || items.length === 0}
        value={selectedId ?? ""}
        onChange={(e) => onChangeSelect(e.target.value)}
        className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 disabled:opacity-60"
      >
        <option value="" disabled>
          {loading ? "Loading…" : items.length === 0 ? "No open acquisitions — create one below" : "Choose acquisition…"}
        </option>
        {items.map((item) => (
          <option key={item.id} value={item.id}>
            {formatAcquisitionOption(item)}
          </option>
        ))}
      </select>

      <div className="mt-4 flex flex-wrap items-end gap-2">
        <div className="min-w-[12rem] flex-1">
          <label className="block text-xs font-semibold uppercase text-slate-500">Quick new group</label>
          <input
            type="text"
            placeholder="e.g. Estate sale June 2026"
            value={newLabel}
            disabled={disabled || creating}
            onChange={(e) => setNewLabel(e.target.value)}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <button
          type="button"
          disabled={disabled || creating || !newLabel.trim()}
          onClick={() => void onCreateQuick()}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100 disabled:opacity-60"
        >
          {creating ? "Creating…" : "Create & select"}
        </button>
      </div>
    </div>
  );
}
