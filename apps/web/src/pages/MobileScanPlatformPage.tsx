import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, apiClient, type P80MobileScanResultRead } from "../api/client";
import { MobileScanResultPanel } from "../components/mobile/p80/MobileScanResultPanel";
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
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-lg items-center justify-between">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-violet-300">P80-01</p>
            <h1 className="text-xl font-semibold text-white">Mobile Scan</h1>
          </div>
          <Link to="/" className="text-sm text-violet-200 underline-offset-2 hover:underline">
            Home
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-lg space-y-6 px-4 py-6 sm:px-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}

        <section className="rounded-3xl border border-slate-700/80 bg-slate-900/70 p-4 shadow-lg">
          <p className="text-xs uppercase tracking-wider text-slate-400">Camera / barcode</p>
          <div className="mt-3 aspect-[4/3] rounded-2xl border border-dashed border-slate-600 bg-slate-950/80 flex items-center justify-center text-center text-sm text-slate-500 px-6">
            Point your device camera at a UPC, ISBN, or ComicOS storage QR label. Use manual entry below when the camera is unavailable.
          </div>
          <form
            className="mt-4 space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void submitScan(barcode);
            }}
          >
            <label className="block text-xs font-medium text-slate-400" htmlFor="mobile-scan-barcode">
              Manual entry
            </label>
            <input
              id="mobile-scan-barcode"
              className="w-full rounded-2xl border border-slate-600 bg-slate-950 px-4 py-3 text-base text-white outline-none focus:border-violet-400"
              placeholder="UPC, ISBN, or comicos://… QR payload"
              value={barcode}
              onChange={(event) => setBarcode(event.target.value)}
              autoComplete="off"
            />
            <button
              type="submit"
              disabled={submitting || !barcode.trim()}
              className="w-full rounded-2xl bg-violet-600 px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
            >
              {submitting ? "Scanning…" : "Scan"}
            </button>
          </form>
        </section>

        {latest ? (
          <section>
            <h2 className="mb-2 text-sm font-semibold text-slate-300">Latest result</h2>
            <MobileScanResultPanel result={latest} />
          </section>
        ) : null}

        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-300">Scan history</h2>
            <button type="button" className="text-xs text-violet-300" onClick={() => void refreshHistory()}>
              Refresh
            </button>
          </div>
          {loading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : history.length === 0 ? (
            <p className="text-sm text-slate-500">No scans yet.</p>
          ) : (
            <ul className="space-y-2">
              {history.map((row) => (
                <li key={row.scan_id}>
                  <Link
                    to={`/mobile-scan/${row.scan_id}`}
                    className="block rounded-2xl border border-slate-700/80 bg-slate-900/50 px-4 py-3 hover:border-violet-500/40"
                  >
                    <p className="font-medium text-white">
                      {row.identification.book?.title ?? row.identification.normalized_barcode}
                    </p>
                    <p className="text-xs text-slate-400">
                      {row.identification.confidence} · {new Date(row.created_at).toLocaleString()}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
