import { useEffect, useState } from "react";

import { ApiError, apiClient, type OrderListResponse, type P80IntakeSessionRead } from "../api/client";
import { MobileOpsShell } from "../components/mobile/p80/MobileOpsShell";
import { StatusBanner } from "../components/StatusBanner";

export function MobileIntakePage(): JSX.Element {
  const [orders, setOrders] = useState<OrderListResponse | null>(null);
  const [orderId, setOrderId] = useState<number | null>(null);
  const [session, setSession] = useState<P80IntakeSessionRead | null>(null);
  const [barcode, setBarcode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void apiClient.getOrders({ page: 1, page_size: 20 }).then(setOrders).catch(() => undefined);
  }, []);

  async function startIntake(mode: "ORDER" | "MANUAL"): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      const row = await apiClient.startMobileIntake({
        intake_mode: mode,
        order_id: mode === "ORDER" ? orderId ?? undefined : undefined,
      });
      setSession(row);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to start intake.");
    } finally {
      setBusy(false);
    }
  }

  async function scan(): Promise<void> {
    if (!session || !barcode.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const result = await apiClient.scanMobileIntake({ session_id: session.session_id, barcode: barcode.trim() });
      if (result.session) {
        setSession(result.session);
      }
      setBarcode("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scan failed.");
    } finally {
      setBusy(false);
    }
  }

  async function finish(): Promise<void> {
    if (!session) return;
    setBusy(true);
    try {
      const result = await apiClient.completeMobileIntake({ session_id: session.session_id });
      setSession({ ...result.session, status: "COMPLETE" });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Complete failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <MobileOpsShell title="Shipment intake">
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
      {!session ? (
        <section className="space-y-3 rounded-2xl border border-slate-700 bg-slate-900/60 p-4">
          <label className="text-xs text-slate-400" htmlFor="intake-order">
            Order (optional)
          </label>
          <select
            id="intake-order"
            className="w-full rounded-xl border border-slate-600 bg-slate-950 px-3 py-2 text-sm"
            value={orderId ?? ""}
            onChange={(e) => setOrderId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Select order…</option>
            {(orders?.items ?? []).map((o) => (
              <option key={o.order_id} value={o.order_id}>
                #{o.order_id} · {o.retailer}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={busy || !orderId}
            className="w-full rounded-2xl bg-violet-600 py-3 text-sm font-semibold disabled:opacity-50"
            onClick={() => void startIntake("ORDER")}
          >
            Start order intake
          </button>
          <button
            type="button"
            disabled={busy}
            className="w-full rounded-2xl border border-slate-600 py-3 text-sm font-semibold"
            onClick={() => void startIntake("MANUAL")}
          >
            Manual intake
          </button>
        </section>
      ) : (
        <>
          <section className="rounded-2xl border border-slate-700 bg-slate-900/60 p-4 text-sm">
            <p>
              Expected: <strong>{session.expected_count}</strong> · Scanned: <strong>{session.scanned_count}</strong> ·
              Received: <strong>{session.received_count}</strong>
            </p>
            <p className="mt-1 text-slate-400">
              Missing: {session.missing_count} · Duplicates: {session.duplicate_scan_count} · Unknown:{" "}
              {session.unknown_scan_count}
            </p>
          </section>
          <input
            className="w-full rounded-2xl border border-slate-600 bg-slate-950 px-4 py-3"
            placeholder="Scan UPC or copy id"
            value={barcode}
            onChange={(e) => setBarcode(e.target.value)}
          />
          <button
            type="button"
            disabled={busy}
            className="w-full rounded-2xl bg-violet-600 py-3 text-sm font-semibold disabled:opacity-50"
            onClick={() => void scan()}
          >
            Scan book
          </button>
          <button type="button" className="w-full rounded-2xl border border-slate-600 py-3 text-sm" onClick={() => void finish()}>
            Done receiving
          </button>
        </>
      )}
    </MobileOpsShell>
  );
}
