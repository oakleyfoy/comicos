import { useState } from "react";

import { ApiError, apiClient, type P79StorageLabelRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function StorageLabelPreviewPage(): JSX.Element {
  const [entityType, setEntityType] = useState("box");
  const [entityId, setEntityId] = useState("");
  const [label, setLabel] = useState<P79StorageLabelRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function preview() {
    setError(null);
    try {
      const body = await apiClient.getStorageLabel(entityType, Number(entityId));
      setLabel(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Label not found.");
    }
  }

  return (
    <AppShell>
      <PageHeader eyebrow="Storage" title="Label Preview" description="QR payload foundation for printable box labels." />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <div className="mb-4 flex flex-wrap gap-2">
        <select
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
        >
          <option value="box">Box</option>
          <option value="shelf">Shelf</option>
          <option value="rack">Rack</option>
          <option value="location">Location</option>
        </select>
        <input
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          placeholder="Entity ID"
          value={entityId}
          onChange={(e) => setEntityId(e.target.value)}
        />
        <button type="button" className="rounded bg-slate-900 px-4 py-2 text-sm text-white" onClick={() => void preview()}>
          Preview
        </button>
      </div>
      {label ? (
        <div className="rounded border border-slate-200 bg-white p-4 text-sm">
          <p className="font-semibold">{label.printable_title}</p>
          <p>{label.storage_path}</p>
          <p className="mt-2 font-mono text-xs">{label.qr_payload}</p>
          <p className="text-slate-500">{label.label_code}</p>
          {label.capacity != null ? (
            <p>
              {label.current_count ?? 0} / {label.capacity}
            </p>
          ) : null}
        </div>
      ) : null}
    </AppShell>
  );
}
