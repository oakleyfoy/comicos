import { useState } from "react";
import { ApiError, apiClient, type P80CollectorScanResultRead } from "../api/client";
import { CollectorAssistantResultPanel } from "../components/mobile/p80/CollectorAssistantResultPanel";
import { PatriotMobilePanel, PatriotMobileShell } from "../components/mobile/p80/PatriotMobileShell";
import { patriotInputClass, patriotPrimaryButtonClass } from "../components/patriotTheme";
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
    <PatriotMobileShell
      eyebrow="P80-03 · Mobile"
      title="Collector Assistant"
      headerLinks={[
        { to: "/convention-mode", label: "Convention" },
        { to: "/collector-dashboard", label: "Dashboard" },
      ]}
    >
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

      <PatriotMobilePanel>
        <p className="text-xs font-semibold uppercase tracking-wider text-red-700">Shopping scan</p>
        <form
          className="mt-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submitScan();
          }}
        >
          <input className={`w-full ${patriotInputClass}`} placeholder="UPC, ISBN, or manual title" value={barcode} onChange={(e) => setBarcode(e.target.value)} />
          <input
            className={`w-full ${patriotInputClass}`}
            placeholder="Vendor price (optional)"
            inputMode="decimal"
            value={vendorPrice}
            onChange={(e) => setVendorPrice(e.target.value)}
          />
          <button type="submit" disabled={submitting} className={`w-full ${patriotPrimaryButtonClass} py-3`}>
            {submitting ? "Evaluating…" : "Scan & evaluate"}
          </button>
        </form>
      </PatriotMobilePanel>

      {result ? (
        <PatriotMobilePanel>
          <CollectorAssistantResultPanel result={result} />
        </PatriotMobilePanel>
      ) : null}
    </PatriotMobileShell>
  );
}
