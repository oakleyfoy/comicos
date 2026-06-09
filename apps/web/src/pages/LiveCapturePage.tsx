import { useEffect, useMemo, useRef, useState } from "react";
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

interface LiveCapturePageProps {
  title: string;
  captureSource: "WEBCAM" | "MOBILE_CAMERA";
  routeLabel: string;
  mirrored?: boolean;
  keyboardShortcuts?: boolean;
}

function frameFingerprintFromVideo(video: HTMLVideoElement): string | null {
  if (!video.videoWidth || !video.videoHeight) {
    return null;
  }
  const canvas = document.createElement("canvas");
  canvas.width = 16;
  canvas.height = 16;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return null;
  }
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
  let hash = 2166136261;
  for (let index = 0; index < data.length; index += 16) {
    const value = Math.floor((data[index] + data[index + 1] + data[index + 2]) / 3);
    hash ^= value;
    hash = Math.imul(hash, 16777619);
  }
  return `f${(hash >>> 0).toString(16)}`;
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

  useEffect(() => {
    let cancelled = false;
    async function loadDevices(): Promise<void> {
      try {
        const mediaDevices = await navigator.mediaDevices.enumerateDevices();
        if (cancelled) {
          return;
        }
        const videoDevices = mediaDevices.filter((device) => device.kind === "videoinput");
        setDevices(videoDevices);
        if (!deviceId && videoDevices.length > 0) {
          setDeviceId(videoDevices[0].deviceId);
        }
      } catch {
        if (!cancelled) {
          setDevices([]);
        }
      }
    }
    void loadDevices();
    return () => {
      cancelled = true;
    };
  }, [deviceId]);

  useEffect(() => {
    if (!session || paused) {
      return;
    }
    const timer = window.setInterval(() => {
      const video = videoRef.current;
      if (!video || inFlightFingerprintRef.current) {
        return;
      }
      const fingerprint = frameFingerprintFromVideo(video);
      if (!fingerprint) {
        return;
      }
      const next = advanceStableFrameTracker(trackerRef.current, fingerprint, 3);
      trackerRef.current = next.tracker;
      setStableState(next.tracker);
      if (!next.accepted) {
        return;
      }
      if (shouldSuppressDuplicateFingerprint(recentFingerprintsRef.current, fingerprint)) {
        setStatusMessage("Duplicate frame suppressed.");
        return;
      }
      inFlightFingerprintRef.current = fingerprint;
      void (async () => {
        try {
          const file = await captureVideoFrame(video, captureSource, fingerprint);
          if (!file) {
            return;
          }
          const uploaded = await apiClient.uploadReceivingSessionImages(session.id, [file], {
            capture_source: captureSource,
            frame_fingerprint: fingerprint,
            stable_frame_count: next.tracker.sameCount,
            frame_sequence_index: session.items.length,
          });
          recentFingerprintsRef.current.add(fingerprint);
          setSession(uploaded.session);
          setStatusMessage(`Captured ${captureSource.replace("_", " ").toLowerCase()}.`);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Unable to upload a live capture frame.");
        } finally {
          inFlightFingerprintRef.current = null;
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
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Capture source</p>
              <p className="mt-2 text-lg font-semibold">{captureSource.replace("_", " ")}</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Stable frames</p>
              <p className="mt-2 text-lg font-semibold">{stableState.sameCount}</p>
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Status</p>
              <p className="mt-2 text-lg font-semibold">{loading ? "Starting session…" : paused ? "Paused" : "Running"}</p>
            </div>
          </div>

          <div className="rounded-[2rem] border border-slate-800 bg-slate-900 p-3 shadow-2xl">
            <div className="relative aspect-[4/3] overflow-hidden rounded-[1.5rem] bg-slate-950">
              <CameraFeed
                videoRef={videoRef}
                deviceId={deviceId}
                mirrored={mirrored}
                className="h-full w-full"
                onError={(message) => setError(message)}
              />
              <RecognitionOverlay
                title={paused ? "Capture paused" : "Point the camera at a comic"}
                subtitle={currentItem ? itemTitle(currentItem) : "Waiting for a stable frame"}
                status={statusMessage}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <label className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-300">
              Camera device
              <select
                className="ml-3 bg-transparent text-white outline-none"
                value={deviceId ?? ""}
                onChange={(event) => setDeviceId(event.target.value || null)}
              >
                <option value="">Default</option>
                {devices.map((device) => (
                  <option key={device.deviceId} value={device.deviceId}>
                    {device.label || `Camera ${device.deviceId.slice(0, 6)}`}
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
