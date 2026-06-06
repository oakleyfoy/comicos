import { useState } from "react";

import { ApiError, apiClient, type P79InventoryLocatorResponse } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function InventoryLocatorPage(): JSX.Element {
  const [q, setQ] = useState("");
  const [result, setResult] = useState<P79InventoryLocatorResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    setError(null);
    try {
      const body = await apiClient.locateInventory(q);
      setResult(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed.");
    }
  }

  return (
    <AppShell>
      <PageHeader eyebrow="Storage" title="Inventory Locator" description="Find exact shelf, box, section, and slot (P79-02)." />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <div className="mb-4 flex gap-2">
        <input
          className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
          placeholder="Title, issue, cert, copy ID, box:ID…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button type="button" className="rounded bg-slate-900 px-4 py-2 text-sm text-white" onClick={() => void search()}>
          Locate
        </button>
      </div>
      {result ? (
        <ul className="space-y-3 text-sm text-slate-700">
          {result.items.map((item) => (
            <li key={item.inventory_copy_id} className="rounded border border-slate-200 bg-white p-3">
              <p className="font-medium">
                {item.title} — {item.assignment_status} ({item.assignment_confidence})
              </p>
              <p className="text-slate-600">{item.path.location_path_text}</p>
              {item.duplicate_matches.length > 0 ? (
                <p className="text-amber-700">Duplicate candidates: {item.duplicate_matches.join(", ")}</p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </AppShell>
  );
}
