import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  createPhotoImportSession,
  getPhotoImportFolderQueue,
  getPhotoImportSession,
  mobilePhotoImportUrl,
  PHOTO_IMPORT_FOLDER_SOURCE,
  photoImportReviewPath,
  processPhotoImportFolderPending,
  resetPhotoImportFolderVision,
  qrCodeUrlForLink,
  uploadPhotoImportImages,
  type PhotoImportFolderQueueStatus,
  type PhotoImportSession,
} from "../../api/photoImport";
import { AppShell } from "../../components/AppShell";
import { PageHeader } from "../../components/PageHeader";
import { StatusBanner } from "../../components/StatusBanner";

const IMAGE_EXT = /\.(jpe?g|png|webp|gif|heic)$/i;

type DirHandle = FileSystemDirectoryHandle & {
  values(): AsyncIterableIterator<FileSystemHandle>;
};

const FOLDER_SESSION_STORAGE_KEY = "comicos.importFolder.sessionToken";

export function AddComicsImportFolderPage(): JSX.Element {
  const navigate = useNavigate();
  const [session, setSession] = useState<PhotoImportSession | null>(null);
  const [queue, setQueue] = useState<PhotoImportFolderQueueStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [folderLabel, setFolderLabel] = useState<string | null>(null);
  const [localIngestBusy, setLocalIngestBusy] = useState(false);
  const [visionResetBusy, setVisionResetBusy] = useState(false);
  const dirHandleRef = useRef<DirHandle | null>(null);
  const seenLocalFilesRef = useRef<Set<string>>(new Set());
  const workerBusyRef = useRef(false);

  const refreshSession = useCallback(async (token: string) => {
    const [row, q] = await Promise.all([getPhotoImportSession(token), getPhotoImportFolderQueue(token)]);
    setSession(row);
    setQueue(q);
    return q;
  }, []);

  const startSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const created = await createPhotoImportSession(PHOTO_IMPORT_FOLDER_SOURCE, "single_comic");
      localStorage.setItem(FOLDER_SESSION_STORAGE_KEY, created.session_token);
      setSession(created);
      await refreshSession(created.session_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start folder import");
    } finally {
      setLoading(false);
    }
  }, [refreshSession]);

  useEffect(() => {
    const saved = localStorage.getItem(FOLDER_SESSION_STORAGE_KEY);
    if (!saved) return;
    setLoading(true);
    void refreshSession(saved)
      .catch(() => localStorage.removeItem(FOLDER_SESSION_STORAGE_KEY))
      .finally(() => setLoading(false));
  }, [refreshSession]);

  const runPipelineTick = useCallback(async (token: string) => {
    if (workerBusyRef.current) return;
    workerBusyRef.current = true;
    try {
      let q = await getPhotoImportFolderQueue(token);
      if (q.pending_uploads > 0 && q.processing === 0) {
        const result = await processPhotoImportFolderPending(token, 2);
        q = result.queue;
      }
      setQueue(q);
      const row = await getPhotoImportSession(token);
      setSession(row);
    } catch {
      /* ignore transient poll errors */
    } finally {
      workerBusyRef.current = false;
    }
  }, []);

  const rerunAccurateVision = useCallback(async () => {
    if (!session?.session_token) return;
    setVisionResetBusy(true);
    setError(null);
    try {
      const result = await resetPhotoImportFolderVision(session.session_token);
      await refreshSession(session.session_token);
      if (result.images_reset > 0) {
        await runPipelineTick(session.session_token);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset GPT reads");
    } finally {
      setVisionResetBusy(false);
    }
  }, [session?.session_token, refreshSession, runPipelineTick]);

  const ingestLocalFolder = useCallback(async () => {
    if (!session?.session_token || !dirHandleRef.current) return;
    const handle = dirHandleRef.current;
    setLocalIngestBusy(true);
    try {
      const batch: File[] = [];
      for await (const entry of handle.values()) {
        if (entry.kind !== "file") continue;
        const fileHandle = entry as FileSystemFileHandle;
        const file = await fileHandle.getFile();
        const key = `${file.name}:${file.size}:${file.lastModified}`;
        if (seenLocalFilesRef.current.has(key)) continue;
        if (!IMAGE_EXT.test(file.name) && !file.type.startsWith("image/")) continue;
        seenLocalFilesRef.current.add(key);
        batch.push(file);
        if (batch.length >= 5) break;
      }
      if (batch.length > 0) {
        await uploadPhotoImportImages(session.session_token, batch);
        await refreshSession(session.session_token);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read ComicOS folder");
    } finally {
      setLocalIngestBusy(false);
    }
  }, [refreshSession, session?.session_token]);

  const connectFolder = useCallback(async () => {
    if (!window.showDirectoryPicker) {
      setError("Use Chrome or Edge on desktop to watch a local ComicOS folder.");
      return;
    }
    try {
      const handle = (await window.showDirectoryPicker({ mode: "readwrite" })) as DirHandle;
      dirHandleRef.current = handle;
      setFolderLabel(handle.name);
      seenLocalFilesRef.current.clear();
      setError(null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Folder access was denied");
    }
  }, []);

  useEffect(() => {
    if (!session?.session_token) return;
    const id = window.setInterval(() => {
      void runPipelineTick(session.session_token);
    }, 4000);
    return () => window.clearInterval(id);
  }, [runPipelineTick, session?.session_token]);

  useEffect(() => {
    if (!session?.session_token || !dirHandleRef.current) return;
    const id = window.setInterval(() => {
      void ingestLocalFolder();
    }, 3000);
    return () => window.clearInterval(id);
  }, [ingestLocalFolder, session?.session_token, folderLabel]);

  const mobileLink = session ? mobilePhotoImportUrl(session.session_token) : "";
  const totalPhotos = session?.uploaded_photo_count ?? 0;
  const queueEmpty = queue?.queue_empty ?? false;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Add Comics"
        title="Import folder"
        description="Scan the QR code once on your phone. Each photo goes into your ComicOS import folder; this computer processes GPT reads, catalog matching, and collection adds in the background until the queue is empty."
      />

      {error ? (
        <div className="mt-6">
          <StatusBanner tone="error">{error}</StatusBanner>
        </div>
      ) : null}

      {!session ? (
        <button
          type="button"
          disabled={loading}
          onClick={() => void startSession()}
          className="mt-8 rounded-xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-60"
        >
          {loading ? "Starting…" : "Start import folder session"}
        </button>
      ) : (
        <div className="mt-8 space-y-8">
          <section className="rounded-2xl border border-white/10 bg-slate-900/70 p-6">
            <div className="flex flex-wrap items-start gap-8">
              <img
                src={qrCodeUrlForLink(mobileLink)}
                alt="QR code to connect phone uploads"
                className="rounded-lg border border-white/10 bg-white p-2"
              />
              <div className="min-w-0 flex-1 space-y-3">
                <p className="text-sm text-slate-300">
                  <strong className="text-white">Phone:</strong> scan once, then shoot one comic per photo. No review on
                  the phone — photos land in the folder automatically.
                </p>
                <p className="text-sm text-slate-400">
                  Session status: <span className="text-slate-200">{session.status}</span> · Photos in folder:{" "}
                  <span className="text-slate-200">{totalPhotos}</span>
                </p>
                <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">Mobile link</label>
                <input
                  readOnly
                  value={mobileLink}
                  className="w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-200"
                  onFocus={(e) => e.target.select()}
                />
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-slate-900/70 p-6">
            <h2 className="text-lg font-semibold text-white">Optional: watch a folder on this PC</h2>
            <p className="mt-2 text-sm text-slate-400">
              If your phone syncs photos to a laptop folder (iCloud, Google Drive, cable copy), choose that folder here.
              New images are uploaded into the same ComicOS queue.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void connectFolder()}
                className="rounded-xl border border-cyan-400/40 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100"
              >
                {folderLabel ? `Watching: ${folderLabel}` : "Choose ComicOS folder…"}
              </button>
              {localIngestBusy ? <span className="text-xs text-slate-500">Checking folder for new photos…</span> : null}
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-slate-900/70 p-6">
            <h2 className="text-lg font-semibold text-white">Background processing</h2>
            {queue ? (
              <dl className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {[
                  ["Waiting", queue.pending_uploads],
                  ["GPT running", queue.processing],
                  ["Done", queue.processed],
                  ["Failed", queue.failed],
                  ["Books read", queue.vision_reads],
                  ["Not in collection yet", queue.pending_inventory],
                ].map(([label, value]) => (
                  <div key={String(label)} className="rounded-xl border border-white/5 bg-slate-950/50 px-3 py-2">
                    <dt className="text-[10px] uppercase tracking-wide text-slate-500">{label}</dt>
                    <dd className="text-xl font-semibold text-white">{value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="mt-2 text-sm text-slate-500">Loading queue…</p>
            )}
            {queueEmpty && totalPhotos > 0 ? (
              <StatusBanner tone="success">
                Queue empty — all photos in this session were processed. Review any exceptions, then start a new session
                if needed.
              </StatusBanner>
            ) : (
              <p className="mt-4 text-sm text-slate-400">
                Keep this tab open while you photograph. ComicOS runs accurate GPT vision, local catalog match, and adds
                matched books to your collection automatically.
              </p>
            )}
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                disabled={visionResetBusy || !session}
                onClick={() => void rerunAccurateVision()}
                className="rounded-xl border border-amber-400/40 bg-amber-400/10 px-4 py-2 text-sm font-semibold text-amber-100 disabled:opacity-50"
              >
                {visionResetBusy ? "Resetting…" : "Re-run GPT on all photos"}
              </button>
              <button
                type="button"
                onClick={() =>
                  navigate(
                    photoImportReviewPath(session.session_token, {
                      exceptionsOnly: true,
                      fromFolder: true,
                    }),
                  )
                }
                className="rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-400"
              >
                Review exceptions
              </button>
              <Link
                to="/dashboard"
                className="rounded-xl border border-white/10 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-white/5"
              >
                Open portfolio
              </Link>
            </div>
          </section>
        </div>
      )}

      <Link to="/add-comics/photo" className="mt-8 inline-block text-sm text-cyan-300 hover:underline">
        ← Phone photo (manual review per shot)
      </Link>
    </AppShell>
  );
}

declare global {
  interface Window {
    showDirectoryPicker?: (options?: { mode?: "read" | "readwrite" }) => Promise<FileSystemDirectoryHandle>;
  }
}
