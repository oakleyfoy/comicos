import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  getPhotoImportSession,
  heartbeatPhotoImportSession,
  uploadPhotoImportImages,
  type PhotoImportSession,
} from "../../api/photoImport";

export function PhotoImportMobilePage(): JSX.Element {
  const { token = "" } = useParams();
  const inputRef = useRef<HTMLInputElement>(null);
  const [session, setSession] = useState<PhotoImportSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const refresh = useCallback(async () => {
    if (!token) return;
    try {
      setSession(await getPhotoImportSession(token));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Session unavailable");
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    void heartbeatPhotoImportSession(token, navigator.userAgent.slice(0, 120)).then(setSession).catch(() => refresh());
  }, [token, refresh]);

  const onFiles = async (files: FileList | null) => {
    if (!files?.length || !token) return;
    const batch = Array.from(files).slice(0, 10);
    setUploading(true);
    setError(null);
    try {
      await uploadPhotoImportImages(token, batch);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">ComicOS Photo Import</p>
      <h1 className="mt-2 text-xl font-semibold">{session ? "Session connected" : "Connecting…"}</h1>
      {session ? (
        <p className="mt-2 text-sm text-slate-400">
          Photos uploaded: {session.uploaded_photo_count} · Detections: {session.detected_book_count}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-4 rounded-lg bg-rose-500/20 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      ) : null}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        className="hidden"
        onChange={(e) => void onFiles(e.target.files)}
      />
      <div className="mt-8 flex flex-col gap-3">
        <button
          type="button"
          disabled={uploading || !token}
          onClick={() => inputRef.current?.click()}
          className="rounded-xl bg-sky-600 py-3 text-sm font-semibold disabled:opacity-50"
        >
          {uploading ? "Uploading…" : "Take Photo / Upload From Camera Roll"}
        </button>
        <p className="text-center text-xs text-slate-500">Up to 10 photos per batch</p>
      </div>
    </div>
  );
}
