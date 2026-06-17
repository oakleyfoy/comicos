import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  createPhotoImportSession,
  getPhotoImportSession,
  mobilePhotoImportUrl,
  qrCodeUrlForLink,
  type PhotoImportSession,
} from "../../api/photoImport";
import { AppShell } from "../../components/AppShell";

export function AddComicsPhotoPage(): JSX.Element {
  const navigate = useNavigate();
  const [session, setSession] = useState<PhotoImportSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const startSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const created = await createPhotoImportSession("desktop");
      setSession(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start session");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!session?.session_token) return;
    const id = window.setInterval(() => {
      void getPhotoImportSession(session.session_token)
        .then(setSession)
        .catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(id);
  }, [session?.session_token]);

  const mobileLink = session ? mobilePhotoImportUrl(session.session_token) : "";
  const reviewReady = (session?.detected_book_count ?? 0) > 0;

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl px-4 py-10">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Add Comics</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Phone Photo Import</h1>
        <p className="mt-3 text-slate-600">
          Start a session on this device, then scan the QR code or open the link on your phone or iPad to upload photos.
        </p>

        {error ? (
          <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </p>
        ) : null}

        {!session ? (
          <button
            type="button"
            disabled={loading}
            onClick={() => void startSession()}
            className="mt-8 rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-60"
          >
            {loading ? "Starting…" : "Start Phone Photo Session"}
          </button>
        ) : (
          <div className="mt-8 space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start gap-6">
              <img src={qrCodeUrlForLink(mobileLink)} alt="QR code for mobile upload" className="rounded-lg border" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-700">Session status: {session.status}</p>
                <p className="mt-1 text-sm text-slate-500">Uploaded photos: {session.uploaded_photo_count}</p>
                <p className="text-sm text-slate-500">Detected books: {session.detected_book_count}</p>
                <label className="mt-4 block text-xs font-semibold uppercase text-slate-500">Mobile link</label>
                <input
                  readOnly
                  value={mobileLink}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  onFocus={(e) => e.target.select()}
                />
                <button
                  type="button"
                  className="mt-2 text-sm font-medium text-blue-700 hover:underline"
                  onClick={() => void navigator.clipboard.writeText(mobileLink)}
                >
                  Copy link
                </button>
              </div>
            </div>
            <button
              type="button"
              disabled={!reviewReady}
              onClick={() => navigate(`/add-comics/photo/session/${session.session_token}`)}
              className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              Review detected books
            </button>
            {!reviewReady ? (
              <p className="text-xs text-slate-500">Review unlocks after at least one detection is ready.</p>
            ) : null}
          </div>
        )}

        <Link to="/add-comics/online-retail" className="mt-8 inline-block text-sm text-blue-700 hover:underline">
          ← Online Retail
        </Link>
      </div>
    </AppShell>
  );
}
