import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type AcquisitionItemRead } from "../api/client";
import { AppShell } from "../components/AppShell";

export function AcquisitionsNeedsReviewPage(): JSX.Element {
  const [items, setItems] = useState<AcquisitionItemRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const resp = await apiClient.acquisitionNeedsReview();
        if (!cancelled) setItems(resp.items);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load needs-review queue.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto max-w-3xl px-4 py-8">
          <Link to="/acquisitions" className="text-sm text-sky-300 hover:underline">
            ← All acquisitions
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-white">Needs Review</h1>
          <p className="text-sm text-slate-400">
            Items added without an exact catalog match. Resolve them when you have a moment.
          </p>

          {error ? (
            <p role="alert" className="mt-4 rounded-lg bg-rose-500/15 px-3 py-2 text-sm text-rose-200">
              {error}
            </p>
          ) : null}

          {loading ? (
            <p className="mt-6 text-sm text-slate-400">Loading…</p>
          ) : items.length === 0 ? (
            <p className="mt-6 text-sm text-slate-400">Nothing to review. 🎉</p>
          ) : (
            <ul className="mt-5 divide-y divide-slate-800 rounded-2xl border border-slate-700 bg-slate-900">
              {items.map((item) => (
                <li key={item.inventory_copy_id} className="flex items-center justify-between gap-3 p-3">
                  <div>
                    <Link
                      to={`/inventory/${item.inventory_copy_id}`}
                      className="font-semibold text-white hover:text-sky-300"
                    >
                      {item.series || "Unknown series"} #{item.issue_number || "?"}
                    </Link>
                    <p className="text-xs text-slate-400">{item.publisher || "Unknown publisher"}</p>
                  </div>
                  <Link
                    to={`/acquisitions/${item.acquisition_id}`}
                    className="rounded-lg border border-slate-600 px-3 py-1 text-xs text-slate-200 hover:border-sky-400"
                  >
                    Open acquisition
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </AppShell>
  );
}
