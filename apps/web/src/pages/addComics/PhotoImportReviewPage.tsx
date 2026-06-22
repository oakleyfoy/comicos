import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  addAllSessionReads,
  addVisionReadToInventory,
  catalogMatchVisionRead,
  chooseVisionReadMatch,
  getPhotoImportSession,
  listSessionVisionReads,
  originalImageUrl,
  rematchVisionRead,
  rereadVisionRead,
  submitVisionReadFeedback,
  updateVisionRead,
  type PhotoImportSession,
  type PhotoImportVisionRead,
  type PhotoImportVisionReadUpdate,
} from "../../api/photoImport";
import { AppShell } from "../../components/AppShell";

type Draft = {
  publisher: string;
  series: string;
  issue_number: string;
  issue_title: string;
  variant_description: string;
  year: string;
  cover_date: string;
  barcode: string;
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

function catalogDisagreesWithGpt(read: PhotoImportVisionRead): boolean {
  if (read.catalog_issue_id == null || !read.series?.trim() || !read.catalog_series?.trim()) {
    return false;
  }
  const gpt = read.series.trim().toLowerCase();
  const cat = read.catalog_series.trim().toLowerCase();
  return gpt !== cat && !gpt.includes(cat) && !cat.includes(gpt);
}

function displayTitleForRead(read: PhotoImportVisionRead): string {
  const matched = read.catalog_issue_id != null;
  if (!matched) {
    return `${read.series ?? "Unknown"} ${read.issue_number ? `#${read.issue_number}` : ""}`.trim();
  }
  if (catalogDisagreesWithGpt(read)) {
    return `${read.series ?? "Unknown"} #${read.issue_number ?? read.catalog_issue_number ?? "?"}`;
  }
  return `${read.catalog_series ?? read.series ?? "Unknown"} #${read.catalog_issue_number ?? read.issue_number ?? "?"}`;
}

function groupByImage(reads: PhotoImportVisionRead[]): { imageId: number; books: PhotoImportVisionRead[] }[] {
  const order: number[] = [];
  const map = new Map<number, PhotoImportVisionRead[]>();
  for (const read of reads) {
    if (!map.has(read.image_id)) {
      map.set(read.image_id, []);
      order.push(read.image_id);
    }
    map.get(read.image_id)!.push(read);
  }
  return order.map((imageId) => ({
    imageId,
    books: (map.get(imageId) ?? []).sort(
      (a, b) => (a.detection_index ?? 0) - (b.detection_index ?? 0) || a.id - b.id,
    ),
  }));
}

function catalogSearchCompleted(read: PhotoImportVisionRead): boolean {
  return read.match_method != null && read.match_method !== "";
}

export function PhotoImportReviewPage(): JSX.Element {
  const { token = "" } = useParams<{ token: string }>();
  const [reads, setReads] = useState<PhotoImportVisionRead[]>([]);
  const [sessionInfo, setSessionInfo] = useState<PhotoImportSession | null>(null);
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const knownReadIds = useRef<Set<number>>(new Set());

  const seedDrafts = useCallback((rows: PhotoImportVisionRead[]) => {
    setDrafts((prev) => {
      const next = { ...prev };
      for (const row of rows) {
        if (!knownReadIds.current.has(row.id)) {
          next[row.id] = draftFromRead(row);
          knownReadIds.current.add(row.id);
        }
      }
      return next;
    });
  }, []);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [rows, sessionRow] = await Promise.all([
        listSessionVisionReads(token),
        getPhotoImportSession(token),
      ]);
      setReads(rows);
      setSessionInfo(sessionRow);
      seedDrafts(rows);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load GPT reads");
    }
  }, [token, seedDrafts]);

  useEffect(() => {
    void load();
    const id = window.setInterval(() => void load(), 2000);
    return () => window.clearInterval(id);
  }, [load]);

  const applyRead = (updated: PhotoImportVisionRead) => {
    setReads((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
  };

  const replacePhotoReads = (imageId: number, rows: PhotoImportVisionRead[]) => {
    setReads((prev) => [...prev.filter((r) => r.image_id !== imageId), ...rows]);
    for (const row of rows) {
      knownReadIds.current.delete(row.id);
    }
    seedDrafts(rows);
  };

  const setField = (readId: number, key: keyof Draft) => (value: string) =>
    setDrafts((d) => ({ ...d, [readId]: { ...(d[readId] ?? ({} as Draft)), [key]: value } }));

  const saveEdits = async (read: PhotoImportVisionRead) => {
    setBusyId(read.id);
    setNotice(null);
    try {
      const payload: PhotoImportVisionReadUpdate = { ...drafts[read.id] };
      await updateVisionRead(read.id, payload);
      const rematched = await rematchVisionRead(read.id);
      applyRead(rematched);
      setNotice("Saved changes and refreshed catalog match.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save changes");
    } finally {
      setBusyId(null);
    }
  };

  const findInCatalog = async (read: PhotoImportVisionRead) => {
    setBusyId(read.id);
    setNotice(null);
    try {
      await updateVisionRead(read.id, { ...drafts[read.id] });
      const updated = await catalogMatchVisionRead(read.id);
      applyRead(updated);
      if (updated.catalog_issue_id != null) {
        setNotice("Found a catalog match.");
      } else {
        setNotice("No catalog match — we checked our database and ComicVine. You can add without a cover.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Catalog search failed");
    } finally {
      setBusyId(null);
    }
  };

  const addToInventory = async (read: PhotoImportVisionRead) => {
    setBusyId(read.id);
    setNotice(null);
    try {
      const saved = await updateVisionRead(read.id, { ...drafts[read.id] });
      applyRead(saved);
      const result = await addVisionReadToInventory(read.id);
      applyRead(result.vision_read);
      setNotice(
        `Added to your collection (${result.created_count} cop${result.created_count === 1 ? "y" : "ies"}). Find it in Inventory.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add to inventory");
    } finally {
      setBusyId(null);
    }
  };

  const addAll = async () => {
    setBulkBusy(true);
    setNotice(null);
    try {
      const result = await addAllSessionReads(token);
      setNotice(
        `Added ${result.added_count} book${result.added_count === 1 ? "" : "s"} (${result.total_copies} cop${result.total_copies === 1 ? "y" : "ies"}) to your collection.`,
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add all to inventory");
    } finally {
      setBulkBusy(false);
    }
  };

  const rereadPhoto = async (read: PhotoImportVisionRead) => {
    setBusyId(read.id);
    setNotice(null);
    try {
      const rows = await rereadVisionRead(read.id);
      replacePhotoReads(read.image_id, rows);
      setNotice(`GPT re-read this photo — found ${rows.length} book${rows.length === 1 ? "" : "s"}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not re-read photo");
    } finally {
      setBusyId(null);
    }
  };

  const chooseMatch = async (read: PhotoImportVisionRead, catalogIssueId: number) => {
    setBusyId(read.id);
    try {
      const updated = await chooseVisionReadMatch(read.id, catalogIssueId);
      applyRead(updated);
      setNotice("Switched the catalog match.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not switch match");
    } finally {
      setBusyId(null);
    }
  };

  const sendFeedback = async (read: PhotoImportVisionRead, isCorrect: boolean) => {
    setBusyId(read.id);
    try {
      const updated = await submitVisionReadFeedback(read.id, { is_correct: isCorrect });
      applyRead(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save feedback");
    } finally {
      setBusyId(null);
    }
  };

  const uploadedCount = sessionInfo?.uploaded_photo_count ?? 0;
  const photos = groupByImage(reads);
  const waitingForGpt = uploadedCount > photos.length;
  const pendingCount = reads.filter((r) => !r.added_to_inventory).length;

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Add Comics</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">Phone Photo Import — GPT review</h1>
        <p className="mt-2 text-sm text-slate-600">
          GPT reads each photo first (publisher, series, issue, year, barcode). When the fields look right, click{" "}
          <strong className="font-medium">Find in catalog</strong> — we search our database, then ComicVine once if needed.
          Add to your collection with a cover when matched, or without a catalog cover if not.
        </p>

        {error ? (
          <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="mt-4 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{notice}</p>
        ) : null}

        {pendingCount > 0 ? (
          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              disabled={bulkBusy}
              className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50"
              onClick={() => void addAll()}
            >
              {bulkBusy ? "Adding…" : `Add all to collection (${pendingCount})`}
            </button>
            <span className="text-sm text-slate-500">
              {photos.length} photo{photos.length === 1 ? "" : "s"} · {reads.length} book
              {reads.length === 1 ? "" : "s"} found
            </span>
          </div>
        ) : null}

        {photos.length === 0 ? (
          <div className="mt-8 space-y-2 text-slate-600">
            {uploadedCount > 0 && waitingForGpt ? (
              <>
                <p className="font-medium text-slate-800">Reading your photos with GPT…</p>
                <p className="text-sm">
                  {photos.length} of {uploadedCount} complete. This page refreshes every few seconds.
                </p>
              </>
            ) : uploadedCount > 0 ? (
              <p>GPT could not load results for your uploads. Check the error above or try uploading again.</p>
            ) : (
              <p>No GPT reads yet — scan the QR code on your phone and photograph your comics.</p>
            )}
          </div>
        ) : (
          <div className="mt-6 space-y-10">
            {photos.map((photo, photoIndex) => (
              <section key={photo.imageId} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-lg font-semibold text-slate-900">
                    Photo {photoIndex + 1} — {photo.books.length} book{photo.books.length === 1 ? "" : "s"} found
                  </h2>
                  <button
                    type="button"
                    disabled={busyId === photo.books[0]?.id}
                    className="rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                    onClick={() => void rereadPhoto(photo.books[0])}
                  >
                    ↻ Re-read with GPT
                  </button>
                </div>

                <div className="mt-4 grid gap-6 lg:grid-cols-[280px_1fr]">
                  <img
                    src={originalImageUrl(token, photo.imageId)}
                    alt={`Uploaded photo ${photoIndex + 1}`}
                    className="max-h-[420px] w-full rounded-xl bg-slate-50 object-contain"
                  />

                  <div className="space-y-5">
                    {photo.books.map((read) => {
                      const draft = drafts[read.id] ?? draftFromRead(read);
                      const matched = read.catalog_issue_id != null;
                      const searched = catalogSearchCompleted(read);
                      const confidencePct =
                        read.confidence != null ? `${Math.round(read.confidence * 100)}%` : null;
                      const busy = busyId === read.id;
                      return (
                        <article
                          key={read.id}
                          className="rounded-xl border border-slate-200 p-4"
                          data-testid={`book-card-${read.id}`}
                        >
                          <div className="flex gap-4">
                            {matched ? (
                              <div className="w-24 shrink-0">
                                <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                                  Catalog cover
                                </span>
                                {read.catalog_cover_url ? (
                                  <img
                                    src={read.catalog_cover_url}
                                    alt="Catalog cover"
                                    className="mt-1 w-24 rounded-lg border border-slate-200 object-cover"
                                  />
                                ) : (
                                  <div className="mt-1 flex h-32 w-24 items-center justify-center rounded-lg border border-dashed border-slate-300 text-center text-[11px] text-slate-400">
                                    No cover image
                                  </div>
                                )}
                              </div>
                            ) : null}

                            <div className="min-w-0 flex-1">
                              <div className="flex items-center justify-between gap-2">
                                <p className="truncate text-sm font-semibold text-slate-900">
                                  {displayTitleForRead(read)}
                                </p>
                                {read.added_to_inventory ? (
                                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                                    In inventory
                                  </span>
                                ) : matched ? (
                                  <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-800">
                                    Catalog match ({read.match_method})
                                  </span>
                                ) : searched ? (
                                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                                    Not in catalog
                                  </span>
                                ) : (
                                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                                    GPT verified
                                  </span>
                                )}
                              </div>
                              {confidencePct ? (
                                <p className="mt-0.5 text-xs text-slate-500">GPT confidence {confidencePct}</p>
                              ) : null}

                              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                <EditField label="Publisher" value={draft.publisher} onChange={setField(read.id, "publisher")} />
                                <EditField label="Series" value={draft.series} onChange={setField(read.id, "series")} />
                                <EditField label="Issue number" value={draft.issue_number} onChange={setField(read.id, "issue_number")} />
                                <EditField label="Issue title" value={draft.issue_title} onChange={setField(read.id, "issue_title")} />
                                <EditField label="Year" value={draft.year} onChange={setField(read.id, "year")} />
                                <EditField label="Barcode" value={draft.barcode} onChange={setField(read.id, "barcode")} />
                              </div>

                              {read.catalog_alternates && read.catalog_alternates.length > 0 ? (
                                <div className="mt-3">
                                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    Other catalog matches
                                  </p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    {read.catalog_alternates.map((alt) => (
                                      <button
                                        key={alt.catalog_issue_id}
                                        type="button"
                                        disabled={busy}
                                        className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                                        onClick={() => void chooseMatch(read, alt.catalog_issue_id)}
                                      >
                                        {alt.series ?? "Unknown"} #{alt.issue_number ?? "?"}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              ) : null}

                              {read.reasoning ? (
                                <p className="mt-3 whitespace-pre-wrap text-xs text-slate-600">{read.reasoning}</p>
                              ) : null}

                              {searched && !matched && !read.added_to_inventory ? (
                                <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                                  Not in our catalog (database + ComicVine). You can still add this copy without a
                                  catalog cover.
                                </p>
                              ) : null}

                              <div className="mt-4 flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  disabled={busy}
                                  className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-800 disabled:opacity-50"
                                  onClick={() => void saveEdits(read)}
                                >
                                  Save changes
                                </button>
                                {!read.added_to_inventory && !matched ? (
                                  <button
                                    type="button"
                                    disabled={busy}
                                    className="rounded-lg bg-sky-700 px-3 py-2 text-sm font-semibold text-white hover:bg-sky-600 disabled:opacity-50"
                                    onClick={() => void findInCatalog(read)}
                                  >
                                    {busy ? "Searching…" : "Find in catalog"}
                                  </button>
                                ) : null}
                                {matched && !read.added_to_inventory ? (
                                  <button
                                    type="button"
                                    disabled={busy}
                                    className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
                                    onClick={() => void addToInventory(read)}
                                  >
                                    Add to collection
                                  </button>
                                ) : null}
                                {searched && !matched && !read.added_to_inventory ? (
                                  <button
                                    type="button"
                                    disabled={busy}
                                    className="rounded-lg bg-amber-700 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-600 disabled:opacity-50"
                                    onClick={() => void addToInventory(read)}
                                  >
                                    Add without catalog cover
                                  </button>
                                ) : null}
                                {read.is_correct == null ? (
                                  <>
                                    <button
                                      type="button"
                                      disabled={busy}
                                      className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                                      onClick={() => void sendFeedback(read, true)}
                                    >
                                      ✓ Correct
                                    </button>
                                    <button
                                      type="button"
                                      disabled={busy}
                                      className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                                      onClick={() => void sendFeedback(read, false)}
                                    >
                                      ✗ Incorrect
                                    </button>
                                  </>
                                ) : (
                                  <span className="self-center text-sm font-medium text-slate-700">
                                    {read.is_correct ? "GPT got this right" : "GPT got this wrong"}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                </div>
              </section>
            ))}
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
