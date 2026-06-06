import { useState } from "react";

import { ApiError, apiClient } from "../api/client";
import { MobileOpsShell } from "../components/mobile/p80/MobileOpsShell";
import { StatusBanner } from "../components/StatusBanner";

export function MobileAuditPage(): JSX.Element {
  const [auditId, setAuditId] = useState<number | null>(null);
  const [boxId, setBoxId] = useState("");
  const [barcode, setBarcode] = useState("");
  const [summary, setSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function start(): Promise<void> {
    if (!boxId) return;
    setError(null);
    try {
      const row = await apiClient.startMobileAudit({
        audit_name: `Box ${boxId} audit`,
        scope_box_id: Number(boxId),
      });
      setAuditId(row.audit_id);
      setSummary(`Expected ${row.expected_count} books`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Start failed.");
    }
  }

  async function scan(): Promise<void> {
    if (!auditId || !barcode.trim()) return;
    setError(null);
    try {
      const row = await apiClient.scanMobileAudit({ audit_id: auditId, barcode: barcode.trim() });
      setSummary(`${row.outcome}: verified ${row.verified_count}, unexpected ${row.unexpected_count}`);
      setBarcode("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scan failed.");
    }
  }

  async function complete(): Promise<void> {
    if (!auditId) return;
    try {
      const row = await apiClient.completeMobileAudit({ audit_id: auditId });
      setSummary(
        `Verified ${row.verified_count} · Missing ${row.missing_count} · Unexpected ${row.unexpected_count} · Accuracy ${row.audit_accuracy_pct}%`,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Complete failed.");
    }
  }

  return (
    <MobileOpsShell title="Box audit">
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      <input
        className="w-full rounded-2xl border border-slate-600 bg-slate-950 px-4 py-3"
        placeholder="Box id"
        value={boxId}
        onChange={(e) => setBoxId(e.target.value)}
      />
      <button type="button" className="w-full rounded-2xl bg-violet-600 py-3 text-sm font-semibold" onClick={() => void start()}>
        Start audit
      </button>
      {auditId ? (
        <>
          <input
            className="w-full rounded-2xl border border-slate-600 bg-slate-950 px-4 py-3"
            placeholder="Scan to verify"
            value={barcode}
            onChange={(e) => setBarcode(e.target.value)}
          />
          <button type="button" className="w-full rounded-2xl border border-slate-600 py-3 text-sm" onClick={() => void scan()}>
            Verify scan
          </button>
          <button type="button" className="w-full rounded-2xl border border-slate-600 py-3 text-sm" onClick={() => void complete()}>
            Complete audit
          </button>
        </>
      ) : null}
      {summary ? <p className="text-sm text-slate-300">{summary}</p> : null}
    </MobileOpsShell>
  );
}
