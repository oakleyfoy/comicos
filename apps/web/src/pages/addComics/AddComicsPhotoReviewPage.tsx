import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  confirmPhotoImportSession,
  listPhotoImportDetections,
  rejectPhotoImportDetection,
  type PhotoImportDetectedBook,
} from "../../api/photoImport";
import { AppShell } from "../../components/AppShell";

const HIGH_CONFIDENCE = 0.85;

export function AddComicsPhotoReviewPage(): JSX.Element {
  const { token = "" } = useParams();
  const [detections, setDetections] = useState<PhotoImportDetectedBook[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setDetections(await listPhotoImportDetections(token));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load detections");
    }
  }, [token]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  const active = detections.filter((d) => d.status !== "rejected" && d.status !== "confirmed");

  const toggle = (id: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const confirmIds = async (ids: number[]) => {
    if (!token || ids.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const items = ids
        .map((id) => {
          const det = detections.find((d) => d.id === id);
          if (!det?.selected_catalog_issue_id) return null;
          return { detected_book_id: id, catalog_issue_id: det.selected_catalog_issue_id, quantity: 1 };
        })
        .filter(Boolean) as { detected_book_id: number; catalog_issue_id: number; quantity: number }[];
      await confirmPhotoImportSession(token, items);
      await load();
      setSelected(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirm failed");
    } finally {
      setBusy(false);
    }
  };

  const confirmHighConfidence = () => {
    const ids = active
      .filter(
        (d) =>
          (d.confidence >= HIGH_CONFIDENCE || (d.ai_confidence ?? 0) >= HIGH_CONFIDENCE) &&
          d.selected_catalog_issue_id &&
          d.candidate_count === 1,
      )
      .map((d) => d.id);
    void confirmIds(ids);
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl px-4 py-10">
        <Link to="/add-comics/photo" className="text-sm text-blue-700 hover:underline">
          ← Phone Photo session
        </Link>
        <h1 className="mt-4 text-2xl font-semibold text-slate-900">Review detected books</h1>
        {error ? (
          <p role="alert" className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => void confirmHighConfidence()}
            className="rounded-lg bg-emerald-700 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Confirm all high confidence
          </button>
          <button
            type="button"
            disabled={busy || selected.size === 0}
            onClick={() => void confirmIds([...selected])}
            className="rounded-lg bg-blue-700 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Confirm selected
          </button>
        </div>
        <ul className="mt-6 space-y-4">
          {active.map((det) => {
            const best = det.best_candidate;
            return (
              <li key={det.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap gap-4">
                  <label className="flex items-start gap-2">
                    <input type="checkbox" checked={selected.has(det.id)} onChange={() => toggle(det.id)} />
                    <span className="text-sm font-medium text-slate-800">
                      {det.ai_series || "Unknown series"} #{det.ai_issue_number || "?"}
                    </span>
                  </label>
                  <div className="flex-1 text-sm text-slate-600">
                    {best ? (
                      <p>
                        Best match: {best.publisher} · {best.series} #{best.issue_number}{" "}
                        <span className="text-slate-400">({Math.round(best.match_score)}%)</span>
                      </p>
                    ) : (
                      <p>No catalog candidates yet.</p>
                    )}
                    <p className="text-xs text-slate-500">Confidence: {Math.round(det.confidence * 100)}%</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy || !det.selected_catalog_issue_id}
                      onClick={() => void confirmIds([det.id])}
                      className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-semibold text-white"
                    >
                      Confirm
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void rejectPhotoImportDetection(det.id).then(() => load())}
                      className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
        {active.length === 0 ? <p className="mt-6 text-sm text-slate-500">No pending detections.</p> : null}
      </div>
    </AppShell>
  );
}
