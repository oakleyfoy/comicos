import { useEffect, useState } from "react";

import { ApiError, apiClient, type P79StorageBoxRead, type P79StorageSearchResultRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function StorageAssignmentPage(): JSX.Element {
  const [boxes, setBoxes] = useState<P79StorageBoxRead[]>([]);
  const [copyId, setCopyId] = useState("");
  const [boxId, setBoxId] = useState("");
  const [slot, setSlot] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [results, setResults] = useState<P79StorageSearchResultRead[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiClient.listStorageBoxes().then((b) => setBoxes(b.items)).catch(() => undefined);
  }, []);

  async function assign() {
    setError(null);
    try {
      await apiClient.assignStorageLocation({
        inventory_copy_id: Number(copyId),
        box_id: Number(boxId),
        slot_number: slot ? Number(slot) : undefined,
        use_suggested_slot: !slot,
      });
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Assignment failed.");
    }
  }

  async function search() {
    setError(null);
    try {
      const body = await apiClient.searchStorage(searchQ);
      setResults(body.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed.");
    }
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Storage"
        title="Storage Assignment"
        description="Assign inventory copies to box slots or use the suggested next slot."
      />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <section className="mb-8 grid gap-3 sm:grid-cols-4">
        <input
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          placeholder="Inventory copy ID"
          value={copyId}
          onChange={(e) => setCopyId(e.target.value)}
        />
        <select
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          value={boxId}
          onChange={(e) => setBoxId(e.target.value)}
        >
          <option value="">Select box</option>
          {boxes.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} (next slot {b.suggested_next_slot ?? "—"})
            </option>
          ))}
        </select>
        <input
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          placeholder="Slot (optional)"
          value={slot}
          onChange={(e) => setSlot(e.target.value)}
        />
        <button type="button" className="rounded bg-slate-900 px-4 py-2 text-sm text-white" onClick={() => void assign()}>
          Assign
        </button>
      </section>
      <section>
        <div className="flex gap-2">
          <input
            className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
            placeholder="Search series, issue, variant, or copy ID"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
          />
          <button type="button" className="rounded border border-slate-300 px-4 py-2 text-sm" onClick={() => void search()}>
            Search
          </button>
        </div>
        <ul className="mt-3 space-y-2 text-sm text-slate-700">
          {results.map((r) => (
            <li key={r.inventory_copy_id}>
              {r.series_name} #{r.issue_number} ({r.variant_label}) — {r.box_name} slot {r.slot_number}:{" "}
              {r.location_path.map((p) => p.name).join(" / ")}
            </li>
          ))}
        </ul>
      </section>
    </AppShell>
  );
}
