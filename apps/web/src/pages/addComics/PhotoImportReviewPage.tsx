import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  addVisionReadToInventory,
  listSessionVisionReads,
  originalImageUrl,
  rereadVisionRead,
  submitVisionReadFeedback,
  updateVisionRead,
  type PhotoImportVisionRead,
  type PhotoImportVisionReadUpdate,
} from "../../api/photoImport";
import { AppShell } from "../../components/AppShell";

type Draft = Required<{
  publisher: string;
  series: string;
  issue_number: string;
  issue_title: string;
  variant_description: string;
  year: string;
  cover_date: string;
  barcode: string;
}>;

const EMPTY_DRAFT: Draft = {
  publisher: "",
  series: "",
  issue_number: "",
  issue_title: "",
  variant_description: "",
  year: "",
  cover_date: "",
  barcode: "",
};

function draftFromRead(read: PhotoImportVisionRead): Draft {
  return {
    publisher: read.publisher ?? "",
    series: read.series ?? "",
    issue_number: read.issue_number ?? "",
    issue_title: read.issue_title ?? "",
    variant_description: read.variant_description ?? "",
    year: read.year ?? "",
    cover_date: read.cover_date ?? "",
    barcode: read.barcode ?? "",
  };
}

function EditField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <input
        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

export function PhotoImportReviewPage(): JSX.Element {
  const { token = "" } = useParams<{ token: string }>();
  const [reads, setReads] = useState<PhotoImportVisionRead[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notes, setNotes] = useState("");
  const draftReadId = useRef<number | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const rows = await listSessionVisionReads(token);
      setReads(rows);
      setError(null);
      setSelectedId((prev) => prev ?? (rows.length ? rows[rows.length - 1].id : null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load GPT reads");
    }
  }, [token]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(id);
  }, [load]);

  const selected = reads.find((r) => r.id === selectedId) ?? reads[reads.length - 1] ?? null;

  // Sync the editable draft only when the selected read changes (avoid clobbering edits on poll).
  useEffect(() => {
    if (selected && draftReadId.current !== selected.id) {
      draftReadId.current = selected.id;
      setDraft(draftFromRead(selected));
      setNotes("");
    }
  }, [selected]);

  const applyRead = (updated: PhotoImportVisionRead) => {
    setReads((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
  };

  const setField = (key: keyof Draft) => (value: string) => setDraft((d) => ({ ...d, [key]: value }));

  const saveEdits = async () => {
    if (!selected) return;
    setBusy(true);
    setNotice(null);
    try {
      const payload: PhotoImportVisionReadUpdate = { ...draft };
      const updated = await updateVisionRead(selected.id, payload);
      applyRead(updated);
      setDraft(draftFromRead(updated));
      setNotice("Saved changes.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save changes");
    } finally {
      setBusy(false);
    }
  };

  const addToInventory = async () => {
    if (!selected) return;
    setBusy(true);
    setNotice(null);
    try {
      // Persist any pending edits first so inventory reflects what the reviewer sees.
      const saved = await updateVisionRead(selected.id, { ...draft });
      applyRead(saved);
      const result = await addVisionReadToInventory(selected.id);
      applyRead(result.vision_read);
      setNotice(`Added to inventory (${result.created_count} cop${result.created_count === 1 ? "y" : "ies"}).`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add to inventory");
    } finally {
      setBusy(false);
    }
  };

  const reread = async () => {
    if (!selected) return;
    setBusy(true);
    setNotice(null);
    try {
      const updated = await rereadVisionRead(selected.id);
      applyRead(updated);
      draftReadId.current = updated.id;
      setDraft(draftFromRead(updated));
      setNotice("GPT re-read this photo.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not re-read photo");
    } finally {
      setBusy(false);
    }
  };

  const sendFeedback = async (isCorrect: boolean) => {
    if (!selected) return;
    setBusy(true);
    try {
      const updated = await submitVisionReadFeedback(selected.id, {
        is_correct: isCorrect,
        feedback_notes: notes.trim() || undefined,
      });
      applyRead(updated);
      setNotes("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save feedback");
    } finally {
      setBusy(false);
    }
  };

  const confidencePct = selected?.confidence != null ? `${Math.round(selected.confidence * 100)}%` : null;

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Add Comics</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">Phone Photo Import — GPT review</h1>
        <p className="mt-2 text-sm text-slate-600">
          Each photo is read by GPT. Review what it found, fix anything, then add it to inventory.
        </p>

        {error ? (
          <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>
        ) : null}

        {reads.length > 1 ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {reads.map((r) => (
              <button
                key={r.id}
                type="button"
                className={`rounded-lg px-3 py-1.5 text-sm ${
                  r.id === selected?.id ? "bg-blue-700 text-white" : "bg-slate-100 text-slate-800"
                }`}
                onClick={() => setSelectedId(r.id)}
              >
                {r.series ?? "Unknown"} {r.issue_number ? `#${r.issue_number}` : ""}
                {r.added_to_inventory ? " ✓" : ""}
              </button>
            ))}
          </div>
        ) : null}

        {!selected ? (
          <p className="mt-8 text-slate-600">
            No GPT reads yet — scan the QR code on your phone and photograph a comic.
          </p>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your photo</p>
              <img
                src={originalImageUrl(token, selected.image_id)}
                alt="Uploaded comic"
                className="mt-3 max-h-[520px] w-full rounded-xl bg-slate-50 object-contain"
              />
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={busy}
                  className="rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                  onClick={() => void reread()}
                >
                  ↻ Re-read with GPT
                </button>
                {confidencePct ? (
                  <span className="text-sm text-slate-500">GPT confidence {confidencePct}</span>
                ) : null}
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">GPT identification</p>
                {selected.added_to_inventory ? (
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                    In inventory
                  </span>
                ) : null}
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <EditField label="Publisher" value={draft.publisher} onChange={setField("publisher")} />
                <EditField label="Series" value={draft.series} onChange={setField("series")} />
                <EditField label="Issue number" value={draft.issue_number} onChange={setField("issue_number")} />
                <EditField label="Issue title" value={draft.issue_title} onChange={setField("issue_title")} />
                <EditField label="Year" value={draft.year} onChange={setField("year")} />
                <EditField label="Cover date" value={draft.cover_date} onChange={setField("cover_date")} />
                <EditField
                  label="Variant"
                  value={draft.variant_description}
                  onChange={setField("variant_description")}
                />
                <EditField label="Barcode" value={draft.barcode} onChange={setField("barcode")} />
              </div>

              {selected.reasoning ? (
                <div className="mt-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">GPT reasoning</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{selected.reasoning}</p>
                </div>
              ) : null}

              {selected.possible_alternates && selected.possible_alternates.length > 0 ? (
                <div className="mt-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Possible alternates (tap to use as series)
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selected.possible_alternates.map((alt) => (
                      <button
                        key={alt}
                        type="button"
                        className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-sm text-slate-700 hover:bg-slate-100"
                        onClick={() => setDraft((d) => ({ ...d, series: alt }))}
                      >
                        {alt}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="mt-5 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={busy}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 disabled:opacity-50"
                  onClick={() => void saveEdits()}
                >
                  Save changes
                </button>
                <button
                  type="button"
                  disabled={busy || selected.added_to_inventory}
                  className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
                  onClick={() => void addToInventory()}
                >
                  {selected.added_to_inventory ? "Added to inventory" : "Add to inventory"}
                </button>
              </div>

              <div className="mt-6 border-t border-slate-100 pt-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Was GPT correct?</p>
                {selected.is_correct != null ? (
                  <p className="mt-2 text-sm font-medium text-slate-700">
                    Feedback recorded: {selected.is_correct ? "GPT got this right" : "GPT got this wrong"}
                  </p>
                ) : (
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                      onClick={() => void sendFeedback(true)}
                    >
                      ✓ Correct
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                      onClick={() => void sendFeedback(false)}
                    >
                      ✗ Incorrect
                    </button>
                  </div>
                )}
                <textarea
                  className="mt-3 w-full rounded-lg border border-slate-200 p-2 text-sm"
                  rows={2}
                  placeholder="Optional feedback notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>
            </div>
          </div>
        )}

        <p className="mt-8 text-sm">
          <Link className="text-blue-700 underline" to="/add-comics/photo">
            ← Back to photo import
          </Link>
        </p>
      </div>
    </AppShell>
  );
}
