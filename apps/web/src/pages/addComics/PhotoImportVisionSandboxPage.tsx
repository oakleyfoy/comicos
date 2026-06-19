import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  listSessionVisionReads,
  originalImageUrl,
  submitVisionReadFeedback,
  type PhotoImportVisionRead,
} from "../../api/photoImport";
import { AppShell } from "../../components/AppShell";

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-slate-900">{value?.trim() ? value : "—"}</dd>
    </div>
  );
}

export function PhotoImportVisionSandboxPage(): JSX.Element {
  const { token = "" } = useParams<{ token: string }>();
  const [reads, setReads] = useState<PhotoImportVisionRead[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState("");

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const rows = await listSessionVisionReads(token);
      setReads(rows);
      if (rows.length && selectedId === null) {
        setSelectedId(rows[rows.length - 1].id);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load vision reads");
    }
  }, [token, selectedId]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  const selected = reads.find((r) => r.id === selectedId) ?? reads[reads.length - 1] ?? null;

  const sendFeedback = async (isCorrect: boolean) => {
    if (!selected) return;
    setBusy(true);
    try {
      const updated = await submitVisionReadFeedback(selected.id, {
        is_correct: isCorrect,
        feedback_notes: notes.trim() || undefined,
      });
      setReads((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setNotes("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save feedback");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">Vision sandbox</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">GPT vision read (no catalog)</h1>
        <p className="mt-2 text-sm text-slate-600">
          Catalog matching, candidates, and inventory are disabled while{" "}
          <code className="rounded bg-slate-100 px-1">PHOTO_IMPORT_VISION_SANDBOX=true</code>.
        </p>
        {error ? <p className="mt-4 text-sm text-red-700">{error}</p> : null}

        {reads.length > 1 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {reads.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`rounded-lg px-3 py-1.5 text-sm ${
                  r.id === selected?.id ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-800"
                }`}
                onClick={() => setSelectedId(r.id)}
              >
                #{r.image_id} {r.series ?? "Unknown"} {r.issue_number ? `#${r.issue_number}` : ""}
              </button>
            ))}
          </div>
        ) : null}

        {!selected ? (
          <p className="mt-8 text-slate-600">No vision reads yet — upload photos from your phone session.</p>
        ) : (
          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your photo</p>
              <img
                src={originalImageUrl(token, selected.image_id)}
                alt="Uploaded comic"
                className="mt-3 max-h-[520px] w-full rounded-xl object-contain bg-slate-50"
              />
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">GPT vision results</p>
              <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                <Field label="Publisher" value={selected.publisher} />
                <Field label="Series" value={selected.series} />
                <Field label="Issue" value={selected.issue_number} />
                <Field
                  label="Confidence"
                  value={
                    selected.confidence != null ? `${Math.round(selected.confidence * 100)}%` : null
                  }
                />
                <Field label="Year" value={selected.year} />
                <Field label="Cover date" value={selected.cover_date} />
                <Field label="Issue title" value={selected.issue_title} />
                <Field label="Variant" value={selected.variant_description} />
                <Field label="Barcode" value={selected.barcode} />
              </dl>
              {selected.reasoning ? (
                <div className="mt-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Reasoning</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{selected.reasoning}</p>
                </div>
              ) : null}
              {selected.is_correct != null ? (
                <p className="mt-4 text-sm font-medium text-slate-700">
                  Feedback recorded: {selected.is_correct ? "GPT got this right" : "GPT got this wrong"}
                </p>
              ) : (
                <div className="mt-6 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                    onClick={() => void sendFeedback(true)}
                  >
                    ✓ GPT got this right
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                    onClick={() => void sendFeedback(false)}
                  >
                    ✗ GPT got this wrong
                  </button>
                </div>
              )}
              <textarea
                className="mt-3 w-full rounded-lg border border-slate-200 p-2 text-sm"
                rows={2}
                placeholder="Optional notes (wrong series, wrong issue, etc.)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>
        )}

        <p className="mt-8 text-sm">
          <Link className="text-indigo-600 underline" to="/add-comics/photo">
            Back to photo import
          </Link>
          {" · "}
          <Link className="text-indigo-600 underline" to="/ops/vision-sandbox">
            Vision sandbox dashboard
          </Link>
        </p>
      </div>
    </AppShell>
  );
}
