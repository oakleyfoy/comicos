import { useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  intakeItemImageUrlByToken,
  uploadIntakeFullCoverPhotoByToken,
} from "../../api/intake";

type Phase = "idle" | "uploading" | "done" | "error";

/**
 * Phone-side capture page reached via the QR / link shown on the desktop review
 * screen. It opens the device camera (native capture), uploads the full cover to
 * the token-authed endpoint, and tells the user to return to the review screen
 * (which polls and refreshes on its own).
 */
export function IntakeFullCoverCapturePage(): JSX.Element {
  const { token = "", itemId = "" } = useParams();
  const numericItemId = Number(itemId);
  const cameraInputRef = useRef<HTMLInputElement | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<string | null>(null);

  const valid = Boolean(token) && Number.isFinite(numericItemId) && numericItemId > 0;

  const onFile = async (file: File | undefined) => {
    if (!file || !valid) return;
    setPhase("uploading");
    setMessage(null);
    try {
      await uploadIntakeFullCoverPhotoByToken(token, numericItemId, file);
      setPhase("done");
    } catch (err) {
      setPhase("error");
      setMessage(err instanceof Error ? err.message : "Upload failed");
    }
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 bg-slate-950 px-6 py-10 text-center text-slate-100">
      <header>
        <h1 className="text-xl font-semibold">Full cover photo</h1>
        <p className="mt-1 text-sm text-slate-400">
          Lay the comic flat, fill the frame with the front cover, and snap a sharp photo.
        </p>
      </header>

      {valid ? (
        <img
          src={intakeItemImageUrlByToken(token, numericItemId)}
          alt="Original scan"
          className="max-h-48 rounded-xl border border-slate-700 object-contain"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
      ) : (
        <p className="text-sm text-rose-300">This capture link is invalid or expired.</p>
      )}

      {phase === "done" ? (
        <div className="rounded-2xl border border-emerald-500/50 bg-emerald-500/10 px-5 py-6">
          <p className="text-base font-semibold text-emerald-200">Sent.</p>
          <p className="mt-1 text-sm text-emerald-100/80">
            Return to your review screen — the item re-identifies automatically.
          </p>
          <button
            type="button"
            className="mt-4 rounded-lg border border-emerald-400/60 px-3 py-1.5 text-xs font-medium text-emerald-100"
            onClick={() => {
              setPhase("idle");
              setMessage(null);
            }}
          >
            Take another
          </button>
        </div>
      ) : (
        <button
          type="button"
          disabled={!valid || phase === "uploading"}
          data-testid="full-cover-capture-open-camera"
          onClick={() => cameraInputRef.current?.click()}
          className="w-full rounded-2xl bg-fuchsia-600 px-4 py-4 text-base font-semibold disabled:opacity-50"
        >
          {phase === "uploading" ? "Uploading…" : "Open Camera"}
        </button>
      )}

      {phase === "error" && message ? (
        <p className="text-sm text-rose-300">{message}</p>
      ) : null}

      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        data-testid="full-cover-capture-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          void onFile(file);
        }}
      />
    </div>
  );
}
