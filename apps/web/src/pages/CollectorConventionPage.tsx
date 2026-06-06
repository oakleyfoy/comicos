import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type P80CollectorScanResultRead } from "../api/client";
import { StatusBanner } from "../components/StatusBanner";

function decisionClass(action: string): string {
  if (action === "BUY") return "bg-emerald-500 text-slate-950";
  if (action === "PASS") return "bg-rose-500 text-white";
  return "bg-slate-700 text-white";
}

export function CollectorConventionPage(): JSX.Element {
  const [barcode, setBarcode] = useState("");
  const [vendorPrice, setVendorPrice] = useState("");
  const [result, setResult] = useState<P80CollectorScanResultRead | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function quickScan(): Promise<void> {
    const trimmed = barcode.trim();
    if (!trimmed) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const vendor = vendorPrice.trim() ? Number.parseFloat(vendorPrice) : undefined;
      const scan = await apiClient.collectorScan({
        barcode: trimmed,
        vendor_price: vendor != null && !Number.isNaN(vendor) ? vendor : undefined,
      });
      setResult(scan);
      setBarcode("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scan failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const book = result?.identification.book;
  const intel = result?.book_intelligence;
  const action = result?.action_card.action ?? "—";

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 px-4 py-3">
        <div className="mx-auto flex max-w-lg items-center justify-between">
          <h1 className="text-lg font-bold tracking-tight">Convention Mode</h1>
          <Link to="/collector-assistant" className="text-sm text-slate-300 underline-offset-2 hover:underline">
            Full assistant
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-lg px-4 py-4 space-y-4">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

        <div className="flex gap-2">
          <input
            className="min-w-0 flex-1 rounded-2xl border-2 border-slate-600 bg-slate-900 px-4 py-4 text-lg"
            placeholder="Scan barcode"
            value={barcode}
            onChange={(e) => setBarcode(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void quickScan();
              }
            }}
          />
          <input
            className="w-24 rounded-2xl border-2 border-slate-600 bg-slate-900 px-2 py-4 text-center text-lg"
            placeholder="$"
            inputMode="decimal"
            value={vendorPrice}
            onChange={(e) => setVendorPrice(e.target.value)}
          />
        </div>
        <button
          type="button"
          disabled={submitting}
          onClick={() => void quickScan()}
          className="w-full rounded-2xl bg-slate-100 py-4 text-lg font-bold text-slate-900 disabled:opacity-50"
        >
          {submitting ? "…" : "Quick scan"}
        </button>

        {result && book ? (
          <section className="space-y-4 pt-2">
            <div>
              <p className="text-2xl font-bold leading-tight">{book.title}</p>
              <p className="text-slate-400">
                Owned: {intel?.ownership.total_copies ?? 0} · FMV{" "}
                {intel?.fmv.authoritative_fmv != null ? `$${intel.fmv.authoritative_fmv.toFixed(0)}` : "—"}
                {result.price_assessment ? ` · Vendor $${result.price_assessment.asking_price.toFixed(0)}` : ""}
              </p>
            </div>
            <div className={`rounded-3xl py-10 text-center text-5xl font-black tracking-tight ${decisionClass(action)}`}>
              {action}
            </div>
            <ul className="space-y-2 text-base text-slate-300">
              {result.action_card.reasons.map((r) => (
                <li key={r}>• {r}</li>
              ))}
            </ul>
          </section>
        ) : null}
      </main>
    </div>
  );
}
