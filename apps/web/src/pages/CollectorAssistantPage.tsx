import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P80CollectorScanResultRead } from "../api/client";
import { CollectorAssistantResultPanel } from "../components/mobile/p80/CollectorAssistantResultPanel";
import { StatusBanner } from "../components/StatusBanner";

export function CollectorAssistantPage(): JSX.Element {
  const [barcode, setBarcode] = useState("");
  const [vendorPrice, setVendorPrice] = useState("");
  const [result, setResult] = useState<P80CollectorScanResultRead | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitScan(): Promise<void> {
    const trimmed = barcode.trim();
    if (!trimmed) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const vendor = vendorPrice.trim() ? Number.parseFloat(vendorPrice) : undefined;
      const payload = {
        barcode: trimmed,
        vendor_price: vendor != null && !Number.isNaN(vendor) ? vendor : undefined,
      };
      const scan = await apiClient.collectorScan(payload);
      setResult(scan);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scan failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-lg items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-emerald-300">P80-03</p>
            <h1 className="text-xl font-semibold text-white">Collector Assistant</h1>
          </div>
          <div className="flex gap-3 text-sm">
            <Link to="/convention-mode" className="text-emerald-200 underline-offset-2 hover:underline">
              Convention
            </Link>
            <Link to="/collector-dashboard" className="text-emerald-200 underline-offset-2 hover:underline">
              Dashboard
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-lg space-y-6 px-4 py-6 sm:px-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

        <section className="rounded-3xl border border-slate-700/80 bg-slate-900/70 p-4 shadow-lg">
          <p className="text-xs uppercase tracking-wider text-slate-400">Shopping scan</p>
          <form
            className="mt-4 space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void submitScan();
            }}
          >
            <input
              className="w-full rounded-xl border border-slate-600 bg-slate-950 px-4 py-3 text-white placeholder:text-slate-500"
              placeholder="UPC, ISBN, or manual title"
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
            />
            <input
              className="w-full rounded-xl border border-slate-600 bg-slate-950 px-4 py-3 text-white placeholder:text-slate-500"
              placeholder="Vendor price (optional)"
              inputMode="decimal"
              value={vendorPrice}
              onChange={(e) => setVendorPrice(e.target.value)}
            />
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-xl bg-emerald-600 py-3 font-semibold text-white disabled:opacity-50"
            >
              {submitting ? "Evaluating…" : "Scan & evaluate"}
            </button>
          </form>
        </section>

        {result ? <CollectorAssistantResultPanel result={result} /> : null}
      </main>
    </div>
  );
}
