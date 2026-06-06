import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, apiClient, type P80MobileScanResultRead } from "../api/client";
import { MobileScanResultPanel } from "../components/mobile/p80/MobileScanResultPanel";
import { StatusBanner } from "../components/StatusBanner";

export function MobileScanResultPage(): JSX.Element {
  const { scanId } = useParams();
  const parsedScanId = Number(scanId);
  const [result, setResult] = useState<P80MobileScanResultRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(parsedScanId)) {
      setError("Invalid scan id.");
      setLoading(false);
      return;
    }
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const row = await apiClient.getMobileScan(parsedScanId);
        setResult(row);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to load scan.");
      } finally {
        setLoading(false);
      }
    })();
  }, [parsedScanId]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto flex max-w-lg items-center gap-3">
          <Link to="/mobile-scan" className="text-sm text-violet-200 hover:underline">
            ← Scan
          </Link>
          <h1 className="text-lg font-semibold">Scan result</h1>
        </div>
      </header>
      <main className="mx-auto max-w-lg px-4 py-6">
        {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
        {loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
        {result ? <MobileScanResultPanel result={result} /> : null}
      </main>
    </div>
  );
}
