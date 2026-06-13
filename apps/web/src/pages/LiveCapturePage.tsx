import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  apiClient,
  type ReceivingSessionDetailRead,
  type ReceivingSessionItemRead,
} from "../api/client";
import { StatusBanner } from "../components/StatusBanner";
import { CameraFeed } from "../components/live-capture/CameraFeed";
import { RecognitionOverlay } from "../components/live-capture/RecognitionOverlay";
import { RecognitionResultCard } from "../components/live-capture/RecognitionResultCard";
import { advanceStableFrameTracker, createStableFrameTracker, shouldSuppressDuplicateFingerprint } from "./liveCaptureState";
import {
  frameFingerprintFromVideo,
  fingerprintsSimilar,
  logLiveCaptureDebug,
} from "./liveCaptureFingerprint";
import {
  formatCaptureMode,
  formatCaptureModeLabel,
  formatDeviceOptionLabel,
  formatLastFrameDisplay,
  formatSessionLabel,
  liveCapturePhaseLabel,
  resolveActiveCameraName,
  resolveLastFrameTimestamp,
  resolveLiveCapturePhase,
} from "./liveCaptureUi";

interface LiveCapturePageProps {
  title: string;
  captureSource: "WEBCAM" | "MOBILE_CAMERA";
  routeLabel: string;
  mirrored?: boolean;
  keyboardShortcuts?: boolean;
}

async function captureVideoFrame(video: HTMLVideoElement, captureSource: string, fingerprint: string): Promise<File | null> {
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return null;
  }
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob((value) => resolve(value), "image/jpeg", 0.92);
  });
  if (!blob) {
    return null;
  }
  return new File([blob], `${captureSource.toLowerCase()}-${fingerprint}.jpg`, { type: "image/jpeg" });
}

function itemTitle(item: ReceivingSessionItemRead): string {
  const candidate = item.selected_candidate_json;
  if (candidate && typeof candidate === "object") {
    const series = String((candidate as Record<string, unknown>).series ?? "Unknown");
    const issue = String((candidate as Record<string, unknown>).issue_number ?? "?");
    return `${series} #${issue}`;
  }
  const snapshot = item.recognition_snapshot_json as Record<string, unknown>;
  const series = String(snapshot.series ?? "Unknown");
  const issue = String(snapshot.issue_number ?? "?");
  return `${series} #${issue}`;
}

function LiveCapturePageInner({
  title,
  captureSource,
  routeLabel,
  mirrored = false,
  keyboardShortcuts = false,
}: LiveCapturePageProps): JSX.Element {
  const videoRef = useRef<HTMLVideoElement>(null);
  const trackerRef = useRef(createStableFrameTracker());
  const recentFingerprintsRef = useRef<Set<string>>(new Set());
  const inFlightFingerprintRef = useRef<string | null>(null);
  const [session, setSession] = useState<ReceivingSessionDetailRead | null>(null);
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraReady, setCameraReady] = useState(false);
  const [recognizing, setRecognizing] = useState(false);
  const [lastFrameCapturedAt, setLastFrameCapturedAt] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("Ready to capture.");
  const [stableState, setStableState] = useState(trackerRef.current);
  const retryTimerRef = useRef<number | null>(null);
  const sessionAttemptRef = useRef(0);

  const currentItem = useMemo(
    () => session?.items.find((item) => item.status !== "CONFIRMED" && item.status !== "SKIPPED") ?? null,
    [session],
  );

  useEffect(() => {
    let cancelled = false;
    const startSession = async (): Promise<void> => {
      setLoading(true);
      try {
        const created = await apiClient.createReceivingSession({ capture_source: captureSource });
        const sessionId = created?.id;
        if (typeof sessionId !== "number") {
          throw new Error("Invalid receiving session response: missing session id.");
        }
        const detail = await apiClient.getReceivingSession(sessionId);
        if (cancelled) {
          return;
        }
        sessionAttemptRef.current = 0;
        setSession(detail);
        setError(null);
        setStatusMessage("Live capture session ready.");
      } catch (err) {
        if (cancelled) {
          return;
        }
        const message = err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Unable to start a live capture session.";
        if (message.includes("missing session id")) {
          setError(message);
          setStatusMessage("Live session response was invalid.");
          return;
        }
        const nextAttempt = sessionAttemptRef.current + 1;
        sessionAttemptRef.current = nextAttempt;
        setStatusMessage(`Retrying session creation (${nextAttempt})...`);
        if (nextAttempt >= 4) {
          setError(message);
          return;
        }
        if (retryTimerRef.current != null) {
          window.clearTimeout(retryTimerRef.current);
        }
        retryTimerRef.current = window.setTimeout(() => {
          retryTimerRef.current = null;
          void startSession();
        }, Math.min(1000 * 2 ** (nextAttempt - 1), 8000));
        if (import.meta.env.DEV) {
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void startSession();
    return () => {
      cancelled = true;
      if (retryTimerRef.current != null) {
        window.clearTimeout(retryTimerRef.current);
      }
    };
  }, [captureSource]);

  const refreshDeviceList = useCallback(async (): Promise<void> => {
    try {
      const mediaDevices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = mediaDevices.filter((device) => device.kind === "videoinput");
      setDevices(videoDevices);
      setDeviceId((current) => {
        if (current && videoDevices.some((device) => device.deviceId === current)) {
          return current;
        }
        return videoDevices[0]?.deviceId ?? null;
      });
    } catch {
      setDevices([]);
    }
  }, []);

  useEffect(() => {
    void refreshDeviceList();
  }, [refreshDeviceList]);

  useEffect(() => {
    setCameraReady(false);
    setCameraError(null);
  }, [deviceId]);

  const handleStreamReady = useCallback((): void => {
    setCameraReady(true);
    setCameraError(null);
    void refreshDeviceList();
  }, [refreshDeviceList]);

  const handleCameraError = useCallback((message: string): void => {
    setCameraReady(false);
    setCameraError(message);
  }, []);

  useEffect(() => {
    if (!session || paused) {
      return;
    }
    const timer = window.setInterval(() => {
      logLiveCaptureDebug("capture tick", {
        hasSession: Boolean(session),
        paused,
        inFlight: Boolean(inFlightFingerprintRef.current),
      });
      const video = videoRef.current;
      if (!video || inFlightFingerprintRef.current) {
        return;
      }
      const fingerprint = frameFingerprintFromVideo(video);
      if (!fingerprint) {
        logLiveCaptureDebug("frame extracted", { ok: false, reason: "no fingerprint" });
        return;
      }
      logLiveCaptureDebug("frame extracted", { ok: true, fingerprint });
      const next = advanceStableFrameTracker(trackerRef.current, fingerprint, 3, fingerprintsSimilar);
      trackerRef.current = next.tracker;
      setStableState(next.tracker);
      logLiveCaptureDebug("frame compared", {
        sameCount: next.tracker.sameCount,
        stableIncremented: next.stableIncremented,
        accepted: next.accepted,
      });
      if (next.stableIncremented) {
        logLiveCaptureDebug("stable count incremented", { sameCount: next.tracker.sameCount });
      }
      if (!next.accepted) {
        return;
      }
      if (shouldSuppressDuplicateFingerprint(recentFingerprintsRef.current, fingerprint)) {
        setStatusMessage("Duplicate frame suppressed.");
        logLiveCaptureDebug("capture skipped", { reason: "duplicate fingerprint" });
        return;
      }
      inFlightFingerprintRef.current = fingerprint;
      setRecognizing(true);
      void (async () => {
        try {
          const file = await captureVideoFrame(video, captureSource, fingerprint);
          if (!file) {
            setStatusMessage("Could not encode camera frame for upload.");
            logLiveCaptureDebug("capture failed", { reason: "canvas encode returned null" });
            return;
          }
          logLiveCaptureDebug("uploading frame", { sessionId: session.id, fingerprint });
          const uploaded = await apiClient.uploadReceivingSessionImages(session.id, [file], {
            capture_source: captureSource,
            frame_fingerprint: fingerprint,
            stable_frame_count: next.tracker.sameCount,
            frame_sequence_index: session.items.length,
          });
          recentFingerprintsRef.current.add(fingerprint);
          setSession(uploaded.session);
          const capturedAt = new Date().toISOString();
          setLastFrameCapturedAt(capturedAt);
          setStatusMessage(`Captured ${captureSource.replace("_", " ").toLowerCase()}.`);
          logLiveCaptureDebug("capture complete", { capturedAt });
          trackerRef.current = createStableFrameTracker();
          setStableState(trackerRef.current);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Unable to upload a live capture frame.");
          logLiveCaptureDebug("capture failed", {
            reason: err instanceof Error ? err.message : "upload error",
          });
        } finally {
          inFlightFingerprintRef.current = null;
          setRecognizing(false);
        }
      })();
    }, 250);
    return () => window.clearInterval(timer);
  }, [captureSource, paused, session]);

  async function refreshSession(): Promise<void> {
    if (!session) {
      return;
    }
    setSession(await apiClient.getReceivingSession(session.id));
  }

  async function handleConfirm(decision: "confirm" | "wrong_match" = "confirm"): Promise<void> {
    if (!session || !currentItem) {
      return;
    }
    try {
      const response = await apiClient.confirmReceivingSessionItem(session.id, {
        item_id: currentItem.id,
        decision,
        selected_candidate_index: currentItem.selected_candidate_index ?? 0,
      });
      setSession(response.session);
      setStatusMessage(decision === "confirm" ? "Confirmed current frame." : "Marked for review.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to confirm the current item.");
    }
  }

  async function handleSkip(): Promise<void> {
    if (!session || !currentItem) {
      return;
    }
    try {
      const response = await apiClient.skipReceivingSessionItem(session.id, {
        item_id: currentItem.id,
        reason: "Live capture skip",
      });
      setSession(response.session);
      setStatusMessage("Skipped current frame.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to skip the current item.");
    }
  }

  useEffect(() => {
    if (!keyboardShortcuts) {
      return;
    }
    const handler = (event: KeyboardEvent): void => {
      if (event.key === "Escape") {
        setPaused(true);
        setStatusMessage("Capture paused.");
        return;
      }
      if (paused) {
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        void handleConfirm("confirm");
      } else if (event.key === " ") {
        event.preventDefault();
        void handleSkip();
      } else if (event.key.toLowerCase() === "r") {
        event.preventDefault();
        void handleConfirm("wrong_match");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [keyboardShortcuts, paused, session, currentItem]);

  const liveStats = session?.live_capture_stats_json ?? {};

  const activeCameraName = useMemo(
    () => resolveActiveCameraName(devices, deviceId),
    [deviceId, devices],
  );

  const capturePhase = useMemo(
    () =>
      resolveLiveCapturePhase({
        loading,
        paused,
        cameraError,
        cameraReady,
        recognizing,
        stableCount: stableState.sameCount,
        currentItem,
      }),
    [cameraError, cameraReady, currentItem, loading, paused, recognizing, stableState.sameCount],
  );

  const currentStateLabel = liveCapturePhaseLabel(capturePhase);

  const lastFrameIso = useMemo(
    () => resolveLastFrameTimestamp(session?.items ?? [], lastFrameCapturedAt),
    [lastFrameCapturedAt, session?.items],
  );

  const lastFrameLabel = formatLastFrameDisplay(lastFrameIso);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">{routeLabel}</p>
            <h1 className="text-2xl font-semibold">{title}</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/receiving" className="text-sm text-slate-300 underline-offset-2 hover:underline">
              Receiving station
            </Link>
            <button
              type="button"
              onClick={() => setPaused((value) => !value)}
              className="rounded-full border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100"
            >
              {paused ? "Resume" : "Pause"}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(360px,0.9fr)]">
        <section className="space-y-4">
          {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
          {cameraError ? <StatusBanner tone="error">{cameraError}</StatusBanner> : null}

          <div
            className="rounded-3xl border border-slate-800 bg-slate-900 p-4"
            aria-label="Live capture source and session"
          >
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Active camera</p>
                <p className="mt-1 text-lg font-semibold text-white" data-testid="live-capture-active-camera">
                  {activeCameraName}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Capture mode</p>
                <p className="mt-1 text-lg font-semibold text-white" data-testid="live-capture-mode">
                  {formatCaptureMode(captureSource)}
                </p>
                <p className="text-xs text-slate-400">{formatCaptureModeLabel(captureSource)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Session</p>
                <p className="mt-1 text-lg font-semibold text-white" data-testid="live-capture-session">
                  {formatSessionLabel(session?.id)}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Current state</p>
                <p className="mt-1 text-lg font-semibold text-emerald-300" data-testid="live-capture-state">
                  {currentStateLabel}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Last frame</p>
                <p className="mt-1 text-lg font-semibold text-white" data-testid="live-capture-last-frame">
                  {lastFrameLabel}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Stable frames</p>
                <p className="mt-1 text-lg font-semibold text-white">{stableState.sameCount}</p>
              </div>
            </div>
          </div>

          <div className="rounded-[2rem] border border-slate-800 bg-slate-900 p-3 shadow-2xl">
            <div className="relative aspect-[4/3] overflow-hidden rounded-[1.5rem] bg-slate-950">
              <CameraFeed
                videoRef={videoRef}
                deviceId={deviceId}
                mirrored={mirrored}
                className="h-full w-full"
                onError={handleCameraError}
                onStreamReady={handleStreamReady}
              />
              <RecognitionOverlay
                title={paused ? "Capture paused" : "Point the camera at a comic"}
                subtitle={currentStateLabel}
                status={currentItem ? itemTitle(currentItem) : statusMessage}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <label className="min-w-[min(100%,20rem)] flex-1 rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-300">
              <span className="block text-xs uppercase tracking-[0.2em] text-slate-500">Switch camera</span>
              <span className="mt-1 block text-base font-semibold text-white">
                Selected: {activeCameraName}
              </span>
              <select
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white outline-none"
                aria-label={`Selected camera: ${activeCameraName}`}
                value={deviceId ?? ""}
                onChange={(event) => setDeviceId(event.target.value || null)}
              >
                <option value="">Default camera (system pick)</option>
                {devices.map((device, index) => (
                  <option key={device.deviceId} value={device.deviceId}>
                    {formatDeviceOptionLabel(device, index)}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => void refreshSession()}
              className="rounded-2xl border border-slate-700 px-4 py-3 text-sm font-semibold text-slate-100"
            >
              Refresh queue
            </button>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Frames received</p>
              <p className="mt-2 text-2xl font-semibold">{String(liveStats.live_capture_frames_received ?? 0)}</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Duplicates blocked</p>
              <p className="mt-2 text-2xl font-semibold">{String(liveStats.duplicate_frames_suppressed ?? 0)}</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Average recognize</p>
              <p className="mt-2 text-2xl font-semibold">{String(liveStats.average_recognition_time ?? 0)} ms</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Confirm rate</p>
              <p className="mt-2 text-2xl font-semibold">{String(Math.round((Number(liveStats.confirm_rate ?? 0) || 0) * 100))}%</p>
            </div>
          </div>
        </section>

        <aside className="space-y-4">
          <RecognitionResultCard
            item={currentItem}
            keyboardHint={keyboardShortcuts ? "Enter=Confirm · Space=Skip · R=Review · Esc=Pause" : null}
            onConfirm={() => void handleConfirm("confirm")}
            onSkip={() => void handleSkip()}
            onReview={() => void handleConfirm("wrong_match")}
          />

          <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Queue</p>
            <div className="mt-3 space-y-2">
              {(session?.items ?? []).length === 0 ? (
                <p className="text-sm text-slate-400">No captures yet.</p>
              ) : (
                session?.items.map((item) => (
                  <div key={item.id} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="font-semibold">{itemTitle(item)}</p>
                        <p className="text-xs text-slate-400">
                          {item.recognition_bucket} · {item.status}
                          {item.capture_source ? ` · ${item.capture_source}` : ""}
                        </p>
                      </div>
                      <span className="rounded-full border border-slate-700 px-2 py-1 text-[11px] uppercase tracking-[0.2em] text-slate-400">
                        #{item.sequence_index}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

export function WebcamLiveCapturePage(): JSX.Element {
  return (
    <LiveCapturePageInner
      title="Webcam Receiving"
      routeLabel="P95-04 · Live Capture"
      captureSource="WEBCAM"
      mirrored
      keyboardShortcuts
    />
  );
}

export function MobileLiveCapturePage(): JSX.Element {
  return <LiveCapturePageInner title="Mobile Receiving" routeLabel="P95-04 · Live Capture" captureSource="MOBILE_CAMERA" />;
}
