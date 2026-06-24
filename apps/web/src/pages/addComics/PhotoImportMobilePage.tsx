import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  addVisionReadToInventory,
  catalogMatchVisionReads,
  getPhotoImportImageVerification,
  getPhotoImportSession,
  heartbeatPhotoImportSession,
  PHOTO_IMPORT_FOLDER_SOURCE,
  rereadVisionRead,
  streamPhotoImportVision,
  uploadPhotoImportImages,
  type PhotoImportCaptureMode,
  type PhotoImportScanIntent,
  type PhotoImportImageVerification,
  type PhotoImportSession,
  type PhotoImportVisionRead,
} from "../../api/photoImport";

function formatReadSummary(read: PhotoImportVisionRead): string {
  const series = read.series?.trim() || "Unknown series";
  const num = read.issue_number?.trim() ? ` #${read.issue_number.trim()}` : "";
  return `${series}${num}`;
}

function ReadField({ label, value }: { label: string; value: string | null | undefined }) {
  const text = (value ?? "").trim() || "—";
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-sm text-slate-100">{text}</dd>
    </div>
  );
}

export function PhotoImportMobilePage(): JSX.Element {
  const { token = "" } = useParams();
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const [session, setSession] = useState<PhotoImportSession | null>(null);
  const [captureMode, setCaptureMode] = useState<PhotoImportCaptureMode>("single_comic");
  const [scanIntent, setScanIntent] = useState<PhotoImportScanIntent>("barcode");
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [activeImageId, setActiveImageId] = useState<number | null>(null);
  const [verification, setVerification] = useState<PhotoImportImageVerification | null>(null);
  const [gptReady, setGptReady] = useState(false);
  const [selectedReadIds, setSelectedReadIds] = useState<Set<number>>(new Set());
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [actionReadId, setActionReadId] = useState<number | null>(null);
  const [visionBusy, setVisionBusy] = useState(false);
  const [streamPreview, setStreamPreview] = useState("");

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      const row = await getPhotoImportSession(token);
      setSession(row);
      setCaptureMode(row.capture_mode === "group" ? "group" : "single_comic");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Session unavailable");
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    void heartbeatPhotoImportSession(token, { sourceDevice: navigator.userAgent.slice(0, 120) })
      .then((row) => {
        setSession(row);
        setCaptureMode(row.capture_mode === "group" ? "group" : "single_comic");
      })
      .catch(() => refresh());
  }, [token, refresh]);

  useEffect(() => {
    if (!token || activeImageId == null || visionBusy) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const v = await getPhotoImportImageVerification(token, activeImageId);
        if (cancelled) return;
        setVerification(v);
        const done =
          v.reads.length > 0 &&
          (v.image_status === "processed" || v.image_status === "failed");
        if (done) {
          setGptReady(v.image_status === "processed" && v.reads.length > 0);
          setSelectedReadIds(new Set(v.reads.map((r) => r.id)));
        }
      } catch {
        /* still processing */
      }
    };
    void poll();
    const id = window.setInterval(() => void poll(), 800);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [token, activeImageId, visionBusy]);

  const runQuickVisionStream = async (imageId: number) => {
    setVisionBusy(true);
    setStreamPreview("");
    setGptReady(false);
    setError(null);
    try {
      await streamPhotoImportVision(token, imageId, "quick", {
        onToken: (text) => setStreamPreview((prev) => prev + text),
        onStatus: (data) => {
          if (data.phase === "barcode_scan" || data.vision_mode === "barcode_primary") {
            setStreamPreview("Reading barcode…");
          }
        },
        onDone: (payload) => {
          setVerification(payload);
          setActiveImageId(payload.image_id);
          setGptReady(payload.reads.length > 0 && payload.image_status === "processed");
          setSelectedReadIds(new Set(payload.reads.map((r) => r.id)));
        },
        onError: (message) => setError(message),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "GPT read failed");
    } finally {
      setVisionBusy(false);
    }
  };

  const resetVerification = () => {
    setActiveImageId(null);
    setVerification(null);
    setGptReady(false);
    setStreamPreview("");
    setSelectedReadIds(new Set());
  };

  const setMode = async (mode: PhotoImportCaptureMode) => {
    if (!token || uploading) return;
    setCaptureMode(mode);
    setError(null);
    try {
      const row = await heartbeatPhotoImportSession(token, { captureMode: mode });
      setSession(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update capture mode");
      await refresh();
    }
  };

  const onFiles = async (files: FileList | null, input: HTMLInputElement | null) => {
    if (!files?.length || !token) return;
    const limit = captureMode === "single_comic" ? 1 : 10;
    const batch = Array.from(files).slice(0, limit);
    setUploading(true);
    setError(null);
    resetVerification();
    const folderDrop = session?.source_device === PHOTO_IMPORT_FOLDER_SOURCE;
    try {
      const intent: PhotoImportScanIntent =
        captureMode === "single_comic" && scanIntent === "barcode" ? "barcode" : "cover";
      const saved = await uploadPhotoImportImages(token, batch, intent);
      await refresh();
      if (folderDrop) {
        setActiveImageId(null);
        return;
      }
      for (const img of saved) {
        if (img.id) {
          setActiveImageId(img.id);
          await runQuickVisionStream(img.id);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (input) input.value = "";
    }
  };

  const toggleRead = (readId: number) => {
    setSelectedReadIds((prev) => {
      const next = new Set(prev);
      if (next.has(readId)) next.delete(readId);
      else next.add(readId);
      return next;
    });
  };

  const runCatalogMatch = async () => {
    if (!token || selectedReadIds.size === 0) return;
    setCatalogBusy(true);
    setError(null);
    try {
      const updated = await catalogMatchVisionReads(token, [...selectedReadIds]);
      setVerification((prev) => {
        if (!prev) return prev;
        const byId = new Map(updated.map((r) => [r.id, r]));
        return {
          ...prev,
          reads: prev.reads.map((r) => byId.get(r.id) ?? r),
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Catalog match failed");
    } finally {
      setCatalogBusy(false);
    }
  };

  const rereadPhoto = async () => {
    const first = verification?.reads[0];
    if (!first) return;
    setActionReadId(first.id);
    setError(null);
    try {
      const rows = await rereadVisionRead(first.id);
      setVerification((prev) =>
        prev
          ? {
              ...prev,
              reads: rows,
            }
          : prev,
      );
      setSelectedReadIds(new Set(rows.map((r) => r.id)));
      setGptReady(rows.length > 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-read failed");
    } finally {
      setActionReadId(null);
    }
  };

  const adoptUnmatched = async (readId: number) => {
    setActionReadId(readId);
    setError(null);
    try {
      await addVisionReadToInventory(readId);
      setVerification((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          reads: prev.reads.map((r) =>
            r.id === readId ? { ...r, added_to_inventory: true } : r,
          ),
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add to collection");
    } finally {
      setActionReadId(null);
    }
  };

  const singleComic = captureMode === "single_comic";
  const folderDrop = session?.source_device === PHOTO_IMPORT_FOLDER_SOURCE;
  const useBarcodeScan = singleComic && scanIntent === "barcode" && !folderDrop;
  const captureReady = !folderDrop && gptReady && !uploading && !visionBusy;
  const reads = verification?.reads ?? [];
  const gptPending = !folderDrop && ((activeImageId != null && !gptReady && !uploading) || visionBusy);

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
        {folderDrop ? "ComicOS Import Folder" : "ComicOS Photo Import"}
      </p>
      <h1 className="mt-2 text-xl font-semibold">
        {folderDrop ? "Drop photos into your folder" : "Add Comics From Your Phone"}
      </h1>
      <p className="mt-2 text-sm text-slate-400">
        {folderDrop
          ? "Shoot one comic per photo. Your computer runs GPT and adds books to your collection — no review on this phone."
          : singleComic
            ? useBarcodeScan
              ? "Fill the frame with the UPC barcode — we look up the book in our catalog (no GPT)."
              : "No barcode on the book? Snap the cover — GPT reads title, series, and issue."
            : "One photo can include several comics. GPT lists each book; you choose which to match."}
      </p>

      {!folderDrop ? (
      <fieldset className="mt-6 space-y-2 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Capture mode</legend>
        <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 has-[:checked]:border-sky-500 has-[:checked]:ring-1 has-[:checked]:ring-sky-500/40">
          <input
            type="radio"
            name="capture-mode"
            className="mt-1"
            checked={singleComic}
            disabled={uploading}
            onChange={() => void setMode("single_comic")}
          />
          <span>
            <span className="block text-sm font-semibold text-slate-100">One Comic Per Photo</span>
            <span className="mt-0.5 block text-xs text-emerald-400/90">Recommended</span>
          </span>
        </label>
        <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 has-[:checked]:border-amber-500/80 has-[:checked]:ring-1 has-[:checked]:ring-amber-500/30">
          <input
            type="radio"
            name="capture-mode"
            className="mt-1"
            checked={!singleComic}
            disabled={uploading}
            onChange={() => void setMode("group")}
          />
          <span>
            <span className="block text-sm font-semibold text-slate-100">Multiple comics in one photo</span>
            <span className="mt-0.5 block text-xs text-slate-500">Up to 4+ books — GPT reads each row</span>
          </span>
        </label>
      </fieldset>
      ) : null}

      {!folderDrop && singleComic ? (
        <fieldset className="mt-4 space-y-2 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            How to identify
          </legend>
          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 has-[:checked]:border-sky-500 has-[:checked]:ring-1 has-[:checked]:ring-sky-500/40">
            <input
              type="radio"
              name="scan-intent"
              className="mt-1"
              checked={scanIntent === "barcode"}
              disabled={uploading || visionBusy}
              onChange={() => setScanIntent("barcode")}
            />
            <span>
              <span className="block text-sm font-semibold text-slate-100">Scan barcode</span>
              <span className="mt-0.5 block text-xs text-emerald-400/90">Recommended — one close-up UPC photo</span>
            </span>
          </label>
          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 has-[:checked]:border-amber-500/80 has-[:checked]:ring-1 has-[:checked]:ring-amber-500/30">
            <input
              type="radio"
              name="scan-intent"
              className="mt-1"
              checked={scanIntent === "cover"}
              disabled={uploading || visionBusy}
              onChange={() => setScanIntent("cover")}
            />
            <span>
              <span className="block text-sm font-semibold text-slate-100">No barcode — cover photo</span>
              <span className="mt-0.5 block text-xs text-slate-500">Older books, newsstand without UPC, etc.</span>
            </span>
          </label>
        </fieldset>
      ) : null}

      {session ? (
        <p className="mt-4 text-sm text-slate-400">
          Session connected · Photos: {session.uploaded_photo_count}
          {folderDrop && !uploading ? (
            <span className="block mt-1 text-emerald-300/90">Ready for the next shot.</span>
          ) : null}
        </p>
      ) : (
        <p className="mt-4 text-sm text-slate-500">Connecting to session…</p>
      )}

      {gptPending ? (
        <div className="mt-3 space-y-2" role="status">
          <p className="text-sm text-amber-200/90">
            {useBarcodeScan ? "Looking up barcode…" : "Reading cover (fast mode)…"}
          </p>
          {streamPreview && !useBarcodeScan ? (
            <pre className="max-h-32 overflow-auto rounded-lg bg-slate-900/80 p-2 text-[11px] text-slate-400 whitespace-pre-wrap">
              {streamPreview}
            </pre>
          ) : null}
        </div>
      ) : null}
      {captureReady ? (
        <p
          className="mt-3 rounded-lg bg-emerald-600/25 px-3 py-2 text-sm font-semibold text-emerald-200"
          role="status"
        >
          {useBarcodeScan ? "Book identified — scan the next comic." : "Cover read done — scan the next comic."}
        </p>
      ) : null}

      {reads.length > 0 && !folderDrop ? (
        <section className="mt-6 space-y-4" aria-label="GPT verification">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-slate-200">
              {useBarcodeScan ? "Catalog match" : "What GPT read"}
            </h2>
            <div className="flex flex-wrap gap-2">
              {!useBarcodeScan ? (
                <button
                  type="button"
                  disabled={catalogBusy || actionReadId != null}
                  onClick={() => void rereadPhoto()}
                  className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                >
                  Re-read (accurate)
                </button>
              ) : null}
              <button
                type="button"
                disabled={catalogBusy || selectedReadIds.size === 0}
                onClick={() => void runCatalogMatch()}
                className="rounded-lg bg-sky-700 px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
              >
                {catalogBusy ? "Matching…" : "Find in catalog"}
              </button>
            </div>
          </div>

          {reads.map((read) => {
            const matched = read.catalog_issue_id != null;
            const searched = read.match_method != null && read.match_method !== "";
            const noMatch = searched && !matched;
            const busy = actionReadId === read.id;
            return (
              <article key={read.id} className="rounded-xl border border-slate-800 bg-slate-900/80 p-4">
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={selectedReadIds.has(read.id)}
                    onChange={() => toggleRead(read.id)}
                    aria-label={`Select ${formatReadSummary(read)} for catalog match`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-white">{formatReadSummary(read)}</p>
                    {read.confidence != null && !useBarcodeScan ? (
                      <p className="text-xs text-slate-500">
                        GPT confidence {Math.round(read.confidence * 100)}%
                      </p>
                    ) : null}
                    <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2">
                      <ReadField label="Publisher" value={read.publisher} />
                      <ReadField label="Series" value={read.series} />
                      <ReadField label="Issue #" value={read.issue_number} />
                      <ReadField label="Title" value={read.issue_title} />
                      <ReadField label="Year" value={read.year} />
                      <ReadField label="Barcode" value={read.barcode} />
                    </dl>

                    {matched ? (
                      <div className="mt-4 rounded-lg border border-emerald-800/60 bg-emerald-950/40 p-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-emerald-400/90">
                          Catalog match
                        </p>
                        <div className="mt-2 flex gap-3">
                          {read.catalog_cover_url ? (
                            <img
                              src={read.catalog_cover_url}
                              alt=""
                              className="h-24 w-16 shrink-0 rounded border border-slate-700 object-cover"
                            />
                          ) : null}
                          <div className="text-sm text-slate-200">
                            <p>{read.catalog_series ?? read.series}</p>
                            <p className="text-slate-400">
                              #{read.catalog_issue_number ?? read.issue_number} ·{" "}
                              {read.catalog_publisher ?? read.publisher}
                            </p>
                            {read.added_to_inventory ? (
                              <p className="mt-1 text-xs text-emerald-300">In your collection</p>
                            ) : (
                              <button
                                type="button"
                                disabled={busy}
                                className="mt-2 rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
                                onClick={() => void adoptUnmatched(read.id)}
                              >
                                Add to collection
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    ) : null}

                    {noMatch && !read.added_to_inventory ? (
                      <div className="mt-4 rounded-lg border border-amber-800/50 bg-amber-950/30 p-3 text-sm text-amber-100">
                        <p>Not in our catalog (we checked ComicVine too).</p>
                        <p className="mt-1 text-xs text-amber-200/80">
                          Add it to your collection without a catalog cover?
                        </p>
                        <button
                          type="button"
                          disabled={busy}
                          className="mt-2 rounded-lg bg-amber-700 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                          onClick={() => void adoptUnmatched(read.id)}
                        >
                          Yes, add it
                        </button>
                      </div>
                    ) : null}
                    {read.added_to_inventory && !matched ? (
                      <p className="mt-3 text-xs text-emerald-300">Added to your collection (no catalog cover).</p>
                    ) : null}
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      ) : null}

      {error ? (
        <p role="alert" className="mt-4 rounded-lg bg-rose-500/20 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}

      <input
        ref={cameraInputRef}
        data-testid="photo-import-camera-input"
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => void onFiles(e.target.files, e.target)}
      />
      <input
        ref={galleryInputRef}
        data-testid="photo-import-gallery-input"
        type="file"
        accept="image/*"
        multiple={!singleComic}
        className="hidden"
        onChange={(e) => void onFiles(e.target.files, e.target)}
      />
      <div className="mt-8 flex flex-col gap-3">
        {folderDrop ? (
          <button
            type="button"
            disabled={uploading || !token}
            onClick={() => cameraInputRef.current?.click()}
            className="rounded-xl bg-sky-600 py-4 text-base font-semibold hover:bg-sky-500 disabled:opacity-50"
          >
            {uploading ? "Uploading…" : "Take next photo"}
          </button>
        ) : singleComic ? (
          <button
            type="button"
            disabled={uploading || !token}
            onClick={() => {
              resetVerification();
              cameraInputRef.current?.click();
            }}
            className={`rounded-xl py-4 text-base font-semibold disabled:opacity-50 ${
              captureReady ? "bg-emerald-600 hover:bg-emerald-500" : "bg-sky-600 hover:bg-sky-500"
            }`}
          >
            {uploading ? "Uploading…" : captureReady ? (useBarcodeScan ? "Scan next barcode" : "Scan next comic") : useBarcodeScan ? "Scan barcode" : "Take cover photo"}
          </button>
        ) : (
          <button
            type="button"
            disabled={uploading || !token}
            onClick={() => {
              resetVerification();
              cameraInputRef.current?.click();
            }}
            className={`rounded-xl py-3 text-sm font-semibold disabled:opacity-50 ${
              captureReady ? "bg-emerald-600" : "bg-sky-600"
            }`}
          >
            {uploading ? "Uploading…" : "Take photo"}
          </button>
        )}
        {!folderDrop ? (
        <button
          type="button"
          disabled={uploading || !token}
          onClick={() => {
            resetVerification();
            galleryInputRef.current?.click();
          }}
          className="rounded-xl border border-slate-600 bg-slate-900 py-3 text-sm font-semibold disabled:opacity-50"
        >
          {uploading ? "Uploading…" : useBarcodeScan ? "Choose barcode photo" : singleComic ? "Choose cover photo" : "Upload from library"}
        </button>
        ) : null}
      </div>
    </div>
  );
}
