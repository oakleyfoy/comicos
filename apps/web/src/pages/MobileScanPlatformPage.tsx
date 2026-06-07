import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, apiClient, type P80MobileScanResultRead } from "../api/client";
import { MobileScanResultPanel } from "../components/mobile/p80/MobileScanResultPanel";
import { PatriotMobilePanel, PatriotMobileShell } from "../components/mobile/p80/PatriotMobileShell";
import { patriotInputClass, patriotPrimaryButtonClass } from "../components/patriotTheme";
import { StatusBanner } from "../components/StatusBanner";

export function MobileScanPlatformPage(): JSX.Element {
  const navigate = useNavigate();
  const [barcode, setBarcode] = useState("");
  const [history, setHistory] = useState<P80MobileScanResultRead[]>([]);
  const [latest, setLatest] = useState<P80MobileScanResultRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await apiClient.listMobileScans({ limit: 12, offset: 0 });
      setHistory(list.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load scan history.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  async function submitScan(value: string): Promise<void> {
    const trimmed = value.trim();
    if (!trimmed) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await apiClient.createMobileScan({ barcode: trimmed });
      setLatest(result);
      setBarcode("");
      void refreshHistory();
      navigate(`/mobile-scan/${result.scan_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Scan failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PatriotMobileShell
      eyebrow="P80-01 · Mobile"
      title="Mobile Scan"
      headerLinks={[{ to: "/", label: "Home" }]}
    >
      {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

      <PatriotMobilePanel>
        <p className="text-xs font-semibold uppercase tracking-wider text-red-700">Camera / barcode</p>
        <div className="mt-3 flex aspect-[4/3] items-center justify-center rounded-2xl border border-dashed border-blue-300 bg-blue-50 px-6 text-center text-sm text-blue-800/80">
          Point your device camera at a UPC, ISBN, or ComicOS storage QR label. Use manual entry below when the camera is unavailable.
        </div>
        <form
          className="mt-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void submitScan(barcode);
          }}
        >
          <label className="block text-xs font-medium text-blue-900" htmlFor="mobile-scan-barcode">
            Manual entry
          </label>
          <input
            id="mobile-scan-barcode"
            className={`w-full ${patriotInputClass} py-3 text-base`}
            placeholder="UPC, ISBN, or comicos://… QR payload"
            value={barcode}
            onChange={(event) => setBarcode(event.target.value)}
            autoComplete="off"
          />
          <button type="submit" disabled={submitting || !barcode.trim()} className={`w-full ${patriotPrimaryButtonClass} py-3`}>
            {submitting ? "Scanning…" : "Scan"}
          </button>
        </form>
      </PatriotMobilePanel>

      {latest ? (
        <PatriotMobilePanel>
          <h2 className="mb-2 text-sm font-semibold text-red-700">Latest result</h2>
          <MobileScanResultPanel result={latest} />
        </PatriotMobilePanel>
      ) : null}

      <PatriotMobilePanel>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-red-700">Scan history</h2>
          <button type="button" className="text-xs font-medium text-blue-800 hover:text-red-700" onClick={() => void refreshHistory()}>
            Refresh
          </button>
        </div>
        {loading ? (
          <p className="text-sm text-blue-800/70">Loading…</p>
        ) : history.length === 0 ? (
          <p className="text-sm text-blue-800/70">No scans yet.</p>
        ) : (
          <ul className="space-y-2">
            {history.map((row) => (
              <li key={row.scan_id}>
                <Link
                  to={`/mobile-scan/${row.scan_id}`}
                  className="block rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 hover:border-red-400"
                >
                  <p className="font-medium text-blue-950">
                    {row.identification.book?.title ?? row.identification.normalized_barcode}
                  </p>
                  <p className="text-xs text-blue-800/70">
                    {row.identification.confidence} · {new Date(row.created_at).toLocaleString()}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </PatriotMobilePanel>
    </PatriotMobileShell>
  );
}
