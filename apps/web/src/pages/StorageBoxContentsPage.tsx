import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError, apiClient, type P79BoxContentsRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function StorageBoxContentsPage(): JSX.Element {
  const [searchParams] = useSearchParams();
  const [boxId, setBoxId] = useState(() => searchParams.get("box") ?? "");
  const [contents, setContents] = useState<P79BoxContentsRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fromQuery = searchParams.get("box");
    if (fromQuery) {
      setBoxId(fromQuery);
    }
  }, [searchParams]);

  async function load() {
    setError(null);
    try {
      const body = await apiClient.getStorageBoxContents(Number(boxId));
      setContents(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to load box contents.");
    }
  }

  return (
    <AppShell>
      <PageHeader eyebrow="Storage" title="Box Contents" description="Assigned books by section and slot." />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <div className="mb-4 flex gap-2">
        <input
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          placeholder="Box ID"
          value={boxId}
          onChange={(e) => setBoxId(e.target.value)}
        />
        <button type="button" className="rounded bg-slate-900 px-4 py-2 text-sm text-white" onClick={() => void load()}>
          Open box
        </button>
      </div>
      {contents ? (
        <div className="space-y-4 text-sm">
          <p>
            {contents.box_name}: {contents.total_count}/{contents.capacity} ({contents.utilization_pct}%)
          </p>
          {contents.sections.map((sec) => (
            <div key={sec.section}>
              <h2 className="font-semibold">{sec.section}</h2>
              <ul className="mt-1 space-y-1 text-slate-700">
                {sec.items.map((row) => (
                  <li key={row.inventory_copy_id}>
                    Slot {row.slot_number}: {row.series_name} #{row.issue_number} {row.flag ? `— ${row.flag}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : null}
    </AppShell>
  );
}
