import { useEffect, useState } from "react";

import { ApiError, apiClient, type P79StorageAuditDetailRead } from "../api/client";
import { AppShell } from "../components/AppShell";
import { PageHeader } from "../components/PageHeader";
import { StatusBanner } from "../components/StatusBanner";

export function StorageAuditPage(): JSX.Element {
  const [boxId, setBoxId] = useState("");
  const [audit, setAudit] = useState<P79StorageAuditDetailRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function startAudit() {
    setError(null);
    try {
      const body = await apiClient.createStorageAudit({
        audit_name: `Box ${boxId} audit`,
        scope_box_id: Number(boxId),
      });
      setAudit(body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start audit.");
    }
  }

  async function verify(entryId: number) {
    if (!audit) return;
    const body = await apiClient.verifyStorageAudit(audit.session.id, entryId);
    setAudit(body);
  }

  useEffect(() => {
    void apiClient.listStorageAudits().catch(() => undefined);
  }, []);

  return (
    <AppShell>
      <PageHeader eyebrow="Storage" title="Storage Audit" description="Verify box contents; flag missing or unexpected." />
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <div className="mb-4 flex gap-2">
        <input
          className="rounded border border-slate-300 px-3 py-2 text-sm"
          placeholder="Box ID"
          value={boxId}
          onChange={(e) => setBoxId(e.target.value)}
        />
        <button type="button" className="rounded bg-slate-900 px-4 py-2 text-sm text-white" onClick={() => void startAudit()}>
          Start audit
        </button>
      </div>
      {audit ? (
        <div className="text-sm text-slate-700">
          <p>
            Status: {audit.session.status} — verified {audit.session.verified_count} / expected{" "}
            {audit.session.expected_count}
          </p>
          <ul className="mt-2 space-y-1">
            {audit.entries.map((e) => (
              <li key={e.id} className="flex items-center gap-2">
                {e.title_snapshot} — {e.entry_status}
                {e.entry_status === "EXPECTED" ? (
                  <button type="button" className="text-xs text-blue-700" onClick={() => void verify(e.id)}>
                    Verify
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </AppShell>
  );
}
