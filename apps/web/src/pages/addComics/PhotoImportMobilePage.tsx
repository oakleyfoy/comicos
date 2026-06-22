import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  getPhotoImportSession,
  heartbeatPhotoImportSession,
  uploadPhotoImportImages,
  type PhotoImportCaptureMode,
  type PhotoImportSession,
} from "../../api/photoImport";

export function PhotoImportMobilePage(): JSX.Element {
  const { token = "" } = useParams();
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const [session, setSession] = useState<PhotoImportSession | null>(null);
  const [captureMode, setCaptureMode] = useState<PhotoImportCaptureMode>("single_comic");
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [lastCaptureMessage, setLastCaptureMessage] = useState<string | null>(null);

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
    setLastCaptureMessage(null);
    try {
      await uploadPhotoImportImages(token, batch);
      await refresh();
      if (captureMode === "single_comic") {
        setLastCaptureMessage("Saved — GPT is analyzing this cover (usually under a minute).");
      } else {
        setLastCaptureMessage(
          `Uploaded ${batch.length} photo${batch.length === 1 ? "" : "s"} — analyzing in the background.`,
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (input) input.value = "";
    }
  };

  const singleComic = captureMode === "single_comic";

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">ComicOS Photo Import</p>
      <h1 className="mt-2 text-xl font-semibold">Add Comics From Your Phone</h1>
      <p className="mt-2 text-sm text-slate-400">
        {singleComic
          ? "Photograph one comic cover at a time for the most reliable matches."
          : "Experimental: try to detect multiple comics in one group photo."}
      </p>

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
            <span className="block text-sm font-semibold text-slate-100">Experimental group photo detection</span>
            <span className="mt-0.5 block text-xs text-slate-500">Multiple comics in one shot — beta only</span>
          </span>
        </label>
      </fieldset>

      {session ? (
        <p className="mt-4 text-sm text-emerald-300/90">
          Session connected · Photos: {session.uploaded_photo_count} · Ready for review:{" "}
          {session.detected_book_count}
        </p>
      ) : (
        <p className="mt-4 text-sm text-slate-500">Connecting to session…</p>
      )}
      {lastCaptureMessage ? (
        <p className="mt-3 rounded-lg bg-emerald-500/15 px-3 py-2 text-sm font-medium text-emerald-200" role="status">
          {lastCaptureMessage}
        </p>
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
        {singleComic ? (
          <button
            type="button"
            disabled={uploading || !token}
            onClick={() => cameraInputRef.current?.click()}
            className="rounded-xl bg-sky-600 py-4 text-base font-semibold disabled:opacity-50"
          >
            {uploading ? "Uploading…" : "Take Next Comic Photo"}
          </button>
        ) : (
          <button
            type="button"
            disabled={uploading || !token}
            onClick={() => cameraInputRef.current?.click()}
            className="rounded-xl bg-sky-600 py-3 text-sm font-semibold disabled:opacity-50"
          >
            {uploading ? "Uploading…" : "Take Photo"}
          </button>
        )}
        <button
          type="button"
          disabled={uploading || !token}
          onClick={() => galleryInputRef.current?.click()}
          className="rounded-xl border border-slate-600 bg-slate-900 py-3 text-sm font-semibold disabled:opacity-50"
        >
          {uploading ? "Uploading…" : singleComic ? "Choose One Photo From Library" : "Upload From Photos"}
        </button>
        <p className="text-center text-xs text-slate-500">
          {singleComic
            ? "One cover per upload. Keep shooting — each photo adds another comic to your session."
            : "Use Upload From Photos for camera roll. Up to 10 photos per batch."}
        </p>
      </div>
    </div>
  );
}
