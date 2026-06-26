import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  enqueueIntakeItem,
  getIntakeSession,
  setIntakeSessionStatus,
  type IntakeSession,
} from "../../api/intake";
import {
  createBarcodeVoteState,
  recordBarcodeVote,
  resetBarcodeVotes,
} from "../../lib/barcodeConsensus";

type ScanState = "idle" | "scanning" | "paused" | "stopped";

// Avoid re-enqueuing the same barcode while the book lingers in frame.
const DUPLICATE_WINDOW_MS = 2500;

function quickFeedback(): void {
  try {
    navigator.vibrate?.(40);
  } catch {
    /* ignore */
  }
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    gain.gain.value = 0.05;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.08);
    osc.onended = () => void ctx.close();
  } catch {
    /* ignore */
  }
}

export function IntakeScannerPage(): JSX.Element {
  const { token: tokenParam } = useParams();
  const [session, setSession] = useState<IntakeSession | null>(null);
  const [token, setToken] = useState<string | null>(tokenParam ?? null);
  const [scanState, setScanState] = useState<ScanState>("idle");
  const [scanned, setScanned] = useState(0);
  const [uploadQueue, setUploadQueue] = useState(0);
  const [failed, setFailed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [flash, setFlash] = useState(false);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const lastBarcodeRef = useRef<{ value: string; at: number } | null>(null);
  const detectTimerRef = useRef<number | null>(null);
  const voteStateRef = useRef(createBarcodeVoteState());
  const capturingRef = useRef(false);

  useEffect(() => {
    if (!tokenParam) return;
    void getIntakeSession(tokenParam)
      .then((row) => {
        setSession(row);
        setToken(row.session_token);
        setScanned(row.scanned_count);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Session not found"));
  }, [tokenParam]);

  const stopCamera = useCallback(() => {
    if (detectTimerRef.current != null) {
      window.clearInterval(detectTimerRef.current);
      detectTimerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCameraReady(false);
  }, []);

  const enqueueBlob = useCallback(
    async (blob: Blob, rawBarcode?: string) => {
      if (!token) return;
      setUploadQueue((q) => q + 1);
      setScanned((s) => s + 1); // optimistic, immediate feedback
      setFlash(true);
      window.setTimeout(() => setFlash(false), 120);
      quickFeedback();
      try {
        await enqueueIntakeItem(token, blob, rawBarcode);
      } catch (err) {
        setScanned((s) => Math.max(0, s - 1));
        setFailed((f) => f + 1);
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploadQueue((q) => Math.max(0, q - 1));
      }
    },
    [token],
  );

  const captureFrame = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return null;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return await new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/jpeg", 0.85));
  }, []);

  const manualCapture = useCallback(async () => {
    const blob = await captureFrame();
    if (blob) await enqueueBlob(blob);
  }, [captureFrame, enqueueBlob]);

  // Auto-detect barcodes when supported, so the user never taps while scanning.
  const startDetection = useCallback(() => {
    const Detector = (window as unknown as { BarcodeDetector?: new (opts?: unknown) => { detect: (src: CanvasImageSource) => Promise<{ rawValue: string }[]> } }).BarcodeDetector;
    if (!Detector) return; // manual-capture only
    const detector = new Detector({ formats: ["upc_a", "upc_e", "ean_13", "ean_8"] });
    detectTimerRef.current = window.setInterval(async () => {
      const video = videoRef.current;
      if (!video || video.videoWidth === 0) return;
      try {
        const found = await detector.detect(video);
        if (!found.length) return;
        const value = found[0].rawValue;
        const consensus = recordBarcodeVote(voteStateRef.current, value);
        if (!consensus) return;
        const now = Date.now();
        const last = lastBarcodeRef.current;
        if (last && last.value === consensus.accepted && now - last.at < DUPLICATE_WINDOW_MS) return;
        if (capturingRef.current) return;
        capturingRef.current = true;
        lastBarcodeRef.current = { value: consensus.accepted, at: now };
        const blob = await captureFrame();
        if (blob) await enqueueBlob(blob, consensus.raw);
        resetBarcodeVotes(voteStateRef.current);
        capturingRef.current = false;
      } catch {
        /* detector hiccup; keep scanning */
      }
    }, 500);
  }, [captureFrame, enqueueBlob]);

  const startCamera = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraReady(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: "environment" } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      setCameraReady(true);
      startDetection();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Camera unavailable");
      setCameraReady(false);
    }
  }, [startDetection]);

  const startSession = useCallback(async () => {
    if (!token) {
      setError("Open this page from the QR link on Add Comics → Phone Photo (after choosing an acquisition).");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let active = session;
      if (session?.status !== "active") {
        active = await setIntakeSessionStatus(token, "active");
        setSession(active);
      }
      setScanState("scanning");
      await startCamera();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start session");
    } finally {
      setBusy(false);
    }
  }, [session, token, startCamera]);

  const pauseSession = useCallback(async () => {
    stopCamera();
    setScanState("paused");
    if (token) {
      try {
        const row = await setIntakeSessionStatus(token, "paused");
        setSession(row);
      } catch {
        /* non-fatal */
      }
    }
  }, [stopCamera, token]);

  const stopSession = useCallback(async () => {
    stopCamera();
    setScanState("stopped");
    if (token) {
      try {
        const row = await setIntakeSessionStatus(token, "stopped");
        setSession(row);
      } catch {
        /* non-fatal */
      }
    }
  }, [stopCamera, token]);

  useEffect(() => () => stopCamera(), [stopCamera]);

  const reviewHref = token ? `/intake/review/${token}` : "/intake/review";

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-5 text-slate-100">
      <header className="mb-4">
        <h1 className="text-lg font-semibold">Hands-Free Intake Scanner</h1>
        <p className="text-xs text-slate-400">
          Capture only — books are identified in the background. Review later on desktop.
        </p>
      </header>

      <div className="relative mb-4 overflow-hidden rounded-2xl border border-slate-800 bg-black">
        <video
          ref={videoRef}
          playsInline
          muted
          className="aspect-[3/4] w-full object-cover"
          data-testid="intake-video"
        />
        {flash ? <div className="absolute inset-0 bg-white/70" aria-hidden /> : null}
        {!cameraReady ? (
          <div className="absolute inset-0 flex items-center justify-center text-center text-sm text-slate-400">
            {scanState === "scanning" ? "Starting camera…" : "Camera is off"}
          </div>
        ) : null}
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-xl bg-slate-900 px-2 py-3">
          <div className="text-2xl font-bold text-emerald-400" data-testid="scanned-count">
            {scanned}
          </div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Scanned</div>
        </div>
        <div className="rounded-xl bg-slate-900 px-2 py-3">
          <div className="text-2xl font-bold text-sky-400" data-testid="upload-queue-count">
            {uploadQueue}
          </div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Upload queue</div>
        </div>
        <div className="rounded-xl bg-slate-900 px-2 py-3">
          <div className="text-2xl font-bold text-rose-400" data-testid="failed-count">
            {failed}
          </div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Failed</div>
        </div>
      </div>

      {error ? (
        <p className="mb-3 rounded-lg bg-rose-600/20 px-3 py-2 text-sm text-rose-200">{error}</p>
      ) : null}

      <div className="space-y-3">
        {scanState !== "scanning" ? (
          <button
            type="button"
            onClick={() => void startSession()}
            disabled={busy}
            className="w-full rounded-xl bg-emerald-600 py-4 text-base font-semibold hover:bg-emerald-500 disabled:opacity-50"
          >
            {scanState === "paused" ? "Resume scanning" : "Start session"}
          </button>
        ) : (
          <>
            {cameraReady ? (
              <button
                type="button"
                onClick={() => void manualCapture()}
                className="w-full rounded-xl bg-sky-600 py-5 text-lg font-bold hover:bg-sky-500"
                data-testid="capture-button"
              >
                Capture
              </button>
            ) : (
              <label className="block w-full cursor-pointer rounded-xl bg-sky-600 py-4 text-center text-base font-semibold">
                Capture (camera fallback)
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  data-testid="intake-file-input"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void enqueueBlob(file);
                    e.currentTarget.value = "";
                  }}
                />
              </label>
            )}
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => void pauseSession()}
                className="rounded-xl border border-slate-600 py-3 text-sm font-medium"
              >
                Pause
              </button>
              <button
                type="button"
                onClick={() => void stopSession()}
                className="rounded-xl border border-rose-600/60 py-3 text-sm font-medium text-rose-200"
              >
                Stop
              </button>
            </div>
          </>
        )}

        {token ? (
          <Link
            to={reviewHref}
            className="block rounded-xl border border-slate-700 py-3 text-center text-sm font-medium text-slate-200"
          >
            Open review screen
          </Link>
        ) : null}
      </div>
    </div>
  );
}
