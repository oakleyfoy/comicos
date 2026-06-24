import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createIntakeSession, getIntakeSession, type IntakeSession } from "../../api/intake";
import { qrCodeUrlForLink } from "../../api/photoImport";
import { AppShell } from "../../components/AppShell";

function intakeScannerUrl(token: string): string {
  return `${window.location.origin}/intake/scan/${encodeURIComponent(token)}`;
}

export function AddComicsPhotoPage(): JSX.Element {
  const navigate = useNavigate();
  const [session, setSession] = useState<IntakeSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const startSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const created = await createIntakeSession({ source_device: "desktop" });
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
      void getIntakeSession(session.session_token)
        .then(setSession)
        .catch(() => undefined);
    }, 4000);
    return () => window.clearInterval(id);
  }, [session?.session_token]);

  const scannerLink = session ? intakeScannerUrl(session.session_token) : "";

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl px-4 py-10">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Add Comics</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Phone Photo — Hands-Free Intake</h1>
        <p className="mt-3 text-slate-600">
          Start a session on this device, then scan the QR code on your phone. The phone scanner is{" "}
          <strong className="font-semibold text-slate-800">capture-only</strong>: keep scanning book after book — each
          scan is queued and identified in the background. Review and add to inventory here when you're done.
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
            {loading ? "Starting…" : "Start Intake Session"}
          </button>
        ) : (
          <div className="mt-8 space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start gap-6">
              <img src={qrCodeUrlForLink(scannerLink)} alt="QR code for phone scanner" className="rounded-lg border" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-700">Session status: {session.status}</p>
                <p className="mt-1 text-sm text-slate-500">Scanned: {session.scanned_count}</p>
                <label className="mt-4 block text-xs font-semibold uppercase text-slate-500">Phone scanner link</label>
                <input
                  readOnly
                  value={scannerLink}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  onFocus={(e) => e.target.select()}
                />
                <button
                  type="button"
                  className="mt-2 text-sm font-medium text-blue-700 hover:underline"
                  onClick={() => void navigator.clipboard.writeText(scannerLink)}
                >
                  Copy link
                </button>
              </div>
            </div>
            <button
              type="button"
              onClick={() => navigate(`/intake/review/${session.session_token}`)}
              className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-600"
            >
              Open review screen
            </button>
            <p className="text-xs text-slate-500">
              Books appear in review as they finish processing — you can review while scanning continues.
            </p>
          </div>
        )}

        <Link to="/add-comics/online-retail" className="mt-8 inline-block text-sm text-blue-700 hover:underline">
          ← Online Retail
        </Link>
      </div>
    </AppShell>
  );
}
