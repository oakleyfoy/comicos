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
import { ScannerFramingGuide } from "../components/live-capture/ScannerFramingGuide";
import { RecognitionResultCard } from "../components/live-capture/RecognitionResultCard";
import { RecognitionReviewModal, type RecognitionReviewCloseAction } from "../components/live-capture/RecognitionReviewModal";
import {
  advanceStableFrameTracker,
  createStableFrameTracker,
  hasPendingReceivingItem,
  isCaptureHoldActive,
  nextCaptureHoldUntil,
  receivingActionItemFinalized,
  shouldIgnoreCaptureFailure,
  shouldStartLiveCaptureUpload,
  shouldSurfaceCaptureFailure,
  shouldSuppressDuplicateFingerprint,
} from "./liveCaptureState";
import {
  frameFingerprintFromVideoRegion,
  fingerprintsSimilar,
  logLiveCaptureDebug,
} from "./liveCaptureFingerprint";
import {
  analyzeComicPresenceInGuide,
  captureFramedVideoFrames,
  computeGuideRect,
  mapGuideRectToOverlayStyle,
  resolveFramingGuideStatus,
  type FramingGuideStatus,
  type GuideOverlayStyle,
} from "./liveCaptureFraming";
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
  STABLE_FRAME_THRESHOLD,
} from "./liveCaptureUi";

interface LiveCapturePageProps {
  title: string;
  captureSource: "WEBCAM" | "MOBILE_CAMERA";
  routeLabel: string;
  mirrored?: boolean;
  keyboardShortcuts?: boolean;
}

function isLiveCaptureKeyboardTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
    return true;
  }
  return target.isContentEditable;
}

function shouldAutoOpenReview(item: ReceivingSessionItemRead): boolean {
  const bucket = item.recognition_bucket;
  if (bucket === "REVIEW") {
    return true;
  }
  if (bucket === "UNKNOWN" && (item.candidate_snapshot_json?.length ?? 0) > 0) {
    return true;
  }
  return false;
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

async function tryRecoverReceivingActionSession(
  sessionId: number,
  itemId: number,
): Promise<ReceivingSessionDetailRead | null> {
  try {
    const refreshed = await apiClient.getReceivingSession(sessionId);
    if (receivingActionItemFinalized(refreshed.items, itemId)) {
      return refreshed;
    }
  } catch {
    return null;
  }
  return null;
}

function LiveCapturePageInner({
  title,
  captureSource,
  routeLabel,
  mirrored = false,
  keyboardShortcuts = false,
}: LiveCapturePageProps): JSX.Element {
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraViewportRef = useRef<HTMLDivElement>(null);
  const trackerRef = useRef(createStableFrameTracker());
  const recentFingerprintsRef = useRef<Set<string>>(new Set());
  const inFlightFingerprintRef = useRef<string | null>(null);
  const uploadInFlightRef = useRef(false);
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
  const [framingGuideStatus, setFramingGuideStatus] = useState<FramingGuideStatus>("none");
  const [guideOverlayStyle, setGuideOverlayStyle] = useState<GuideOverlayStyle | null>(null);
  const [manualReviewItemId, setManualReviewItemId] = useState<number | null>(null);
  const [pinnedReviewItemId, setPinnedReviewItemId] = useState<number | null>(null);
  const pausedBeforeReviewRef = useRef(false);
  const [dismissedReviewIds, setDismissedReviewIds] = useState<number[]>([]);
  const [capturedFrameUrl, setCapturedFrameUrl] = useState<string | null>(null);
  const retryTimerRef = useRef<number | null>(null);
  const sessionAttemptRef = useRef(0);
  const sessionRef = useRef<ReceivingSessionDetailRead | null>(null);
  const userActionEpochRef = useRef(0);
  const captureHoldUntilRef = useRef(0);
  const reviewModalOpenRef = useRef(false);
  const capturedFrameUrlRef = useRef<string | null>(null);

  sessionRef.current = session;

  const resetStableFrameTracking = useCallback((): void => {
    trackerRef.current = createStableFrameTracker();
    setStableState(trackerRef.current);
  }, []);

  const armCaptureHoldAfterUserAction = useCallback((): number => {
    userActionEpochRef.current += 1;
    captureHoldUntilRef.current = nextCaptureHoldUntil(Date.now());
    inFlightFingerprintRef.current = null;
    setRecognizing(false);
    uploadInFlightRef.current = false;
    resetStableFrameTracking();
    return userActionEpochRef.current;
  }, [resetStableFrameTracking]);

  const currentItem = useMemo(
    () => session?.items.find((item) => item.status !== "CONFIRMED" && item.status !== "SKIPPED") ?? null,
    [session],
  );

  const reviewModalOpen = useMemo(() => {
    if (!currentItem || !session) {
      return false;
    }
    if (manualReviewItemId === currentItem.id) {
      return true;
    }
    if (dismissedReviewIds.includes(currentItem.id)) {
      return false;
    }
    return shouldAutoOpenReview(currentItem);
  }, [currentItem, dismissedReviewIds, manualReviewItemId, session]);

  reviewModalOpenRef.current = reviewModalOpen;

  const reviewItem = useMemo(() => {
    if (!session || pinnedReviewItemId == null) {
      return null;
    }
    return session.items.find((item) => item.id === pinnedReviewItemId) ?? null;
  }, [pinnedReviewItemId, session]);

  useEffect(() => {
    if (reviewModalOpen) {
      setPinnedReviewItemId((current) => current ?? currentItem?.id ?? null);
      pausedBeforeReviewRef.current = paused;
      armCaptureHoldAfterUserAction();
      setPaused(true);
      return;
    }
    setPinnedReviewItemId(null);
  }, [armCaptureHoldAfterUserAction, currentItem?.id, reviewModalOpen]);

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

  const syncGuideOverlay = useCallback((): void => {
    const video = videoRef.current;
    const container = cameraViewportRef.current;
    if (!video?.videoWidth || !video.videoHeight || !container) {
      setGuideOverlayStyle(null);
      return;
    }
    const rect = computeGuideRect(video.videoWidth, video.videoHeight);
    const { width, height } = container.getBoundingClientRect();
    if (width <= 0 || height <= 0) {
      return;
    }
    setGuideOverlayStyle(
      mapGuideRectToOverlayStyle(video.videoWidth, video.videoHeight, width, height, rect, mirrored),
    );
  }, [mirrored]);

  const handleStreamReady = useCallback((): void => {
    setCameraReady(true);
    setCameraError(null);
    void refreshDeviceList();
    syncGuideOverlay();
  }, [refreshDeviceList, syncGuideOverlay]);

  const handleCameraError = useCallback((message: string): void => {
    setCameraReady(false);
    setCameraError(message);
  }, []);

  useEffect(() => {
    syncGuideOverlay();
    const container = cameraViewportRef.current;
    if (!container) {
      return;
    }
    const observer = new ResizeObserver(() => {
      syncGuideOverlay();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [cameraReady, syncGuideOverlay]);

  useEffect(() => {
    if (!session || paused || reviewModalOpen) {
      return;
    }
    const timer = window.setInterval(() => {
      logLiveCaptureDebug("capture tick", {
        hasSession: Boolean(session),
        paused,
        inFlight: uploadInFlightRef.current,
      });
      if (reviewModalOpenRef.current) {
        logLiveCaptureDebug("capture waiting", { reason: "review modal open" });
        return;
      }
      if (
        !shouldStartLiveCaptureUpload({
          uploadInFlight: uploadInFlightRef.current,
          holdActive: isCaptureHoldActive(captureHoldUntilRef.current, Date.now()),
          hasPendingItem: hasPendingReceivingItem(session.items),
        })
      ) {
        if (uploadInFlightRef.current) {
          logLiveCaptureDebug("capture waiting", { reason: "upload in flight" });
        } else if (isCaptureHoldActive(captureHoldUntilRef.current, Date.now())) {
          logLiveCaptureDebug("capture waiting", { reason: "post-action hold" });
        } else if (hasPendingReceivingItem(session.items)) {
          logLiveCaptureDebug("capture waiting", { reason: "pending item action" });
        }
        return;
      }
      const video = videoRef.current;
      if (!video) {
        return;
      }
      const guideRect = computeGuideRect(video.videoWidth, video.videoHeight);
      const presence = analyzeComicPresenceInGuide(video, guideRect);
      const comicDetected = presence?.detected ?? false;
      setFramingGuideStatus(
        resolveFramingGuideStatus(comicDetected, trackerRef.current.sameCount, STABLE_FRAME_THRESHOLD),
      );

      const fingerprint = frameFingerprintFromVideoRegion(video, guideRect);
      if (!fingerprint) {
        logLiveCaptureDebug("frame extracted", { ok: false, reason: "no fingerprint" });
        setFramingGuideStatus("none");
        return;
      }
      logLiveCaptureDebug("frame extracted", { ok: true, fingerprint, comicDetected });

      if (!comicDetected) {
        trackerRef.current = {
          ...trackerRef.current,
          lastFingerprint: fingerprint,
          sameCount: 0,
        };
        setStableState(trackerRef.current);
        setFramingGuideStatus("none");
        return;
      }

      const next = advanceStableFrameTracker(
        trackerRef.current,
        fingerprint,
        STABLE_FRAME_THRESHOLD,
        fingerprintsSimilar,
      );
      trackerRef.current = next.tracker;
      setStableState(next.tracker);
      setFramingGuideStatus(
        resolveFramingGuideStatus(true, next.tracker.sameCount, STABLE_FRAME_THRESHOLD),
      );
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
      uploadInFlightRef.current = true;
      setRecognizing(true);
      const actionEpochAtStart = userActionEpochRef.current;
      void (async () => {
        try {
          const framed = await captureFramedVideoFrames(video, captureSource, fingerprint, guideRect);
          if (!framed) {
            setStatusMessage("Could not encode camera frame for upload.");
            logLiveCaptureDebug("capture failed", { reason: "canvas encode returned null" });
            return;
          }
          logLiveCaptureDebug("uploading frame", { sessionId: session.id, fingerprint });
          const uploaded = await apiClient.uploadReceivingSessionImages(session.id, [framed.recognition], {
            capture_source: captureSource,
            frame_fingerprint: fingerprint,
            stable_frame_count: next.tracker.sameCount,
            frame_sequence_index: session.items.length,
            diagnostic_image: framed.diagnostic,
            capture_metadata_json: {
              framing_guide: framed.guideRect,
              full_frame_width: video.videoWidth,
              full_frame_height: video.videoHeight,
              recognition_crop_width: framed.guideRect.width,
              recognition_crop_height: framed.guideRect.height,
            },
          });
          recentFingerprintsRef.current.add(fingerprint);
          try {
            const nextFrameUrl = URL.createObjectURL(framed.recognition);
            if (capturedFrameUrlRef.current) {
              URL.revokeObjectURL(capturedFrameUrlRef.current);
            }
            capturedFrameUrlRef.current = nextFrameUrl;
            setCapturedFrameUrl(nextFrameUrl);
          } catch {
            // Object URL preview is best-effort; ignore environments without URL support.
          }
          setSession(uploaded.session);
          const capturedAt = new Date().toISOString();
          setLastFrameCapturedAt(capturedAt);
          setStatusMessage(`Captured ${captureSource.replace("_", " ").toLowerCase()}.`);
          logLiveCaptureDebug("capture complete", { capturedAt });
          resetStableFrameTracking();
        } catch (err) {
          if (shouldIgnoreCaptureFailure(actionEpochAtStart, userActionEpochRef.current)) {
            logLiveCaptureDebug("capture failed ignored", { reason: "user action or stale upload" });
            return;
          }
          const message = err instanceof ApiError ? err.message : "Unable to upload a live capture frame.";
          if (shouldSurfaceCaptureFailure(sessionRef.current?.items)) {
            setError(message);
          } else {
            setStatusMessage(
              message === "Internal server error"
                ? "Auto-capture hit a server error. Pause or point at the next comic."
                : message,
            );
          }
          logLiveCaptureDebug("capture failed", {
            reason: err instanceof Error ? err.message : "upload error",
            surfaced: shouldSurfaceCaptureFailure(sessionRef.current?.items),
          });
        } finally {
          inFlightFingerprintRef.current = null;
          uploadInFlightRef.current = false;
          setRecognizing(false);
        }
      })();
    }, 250);
    return () => window.clearInterval(timer);
  }, [captureSource, paused, resetStableFrameTracking, reviewModalOpen, session]);

  async function refreshSession(): Promise<void> {
    if (!session || reviewModalOpenRef.current) {
      return;
    }
    setSession(await apiClient.getReceivingSession(session.id));
  }

  async function startNewSession(): Promise<void> {
    armCaptureHoldAfterUserAction();
    recentFingerprintsRef.current.clear();
    setLoading(true);
    setError(null);
    try {
      const created = await apiClient.createReceivingSession({ capture_source: captureSource });
      const sessionId = created?.id;
      if (typeof sessionId !== "number") {
        throw new Error("Invalid receiving session response: missing session id.");
      }
      const detail = await apiClient.getReceivingSession(sessionId);
      sessionAttemptRef.current = 0;
      setSession(detail);
      setLastFrameCapturedAt(null);
      setStatusMessage("New live capture session started.");
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Unable to start a new session.";
      setError(message);
      setStatusMessage("Could not start a new session.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm(decision: "confirm" | "wrong_match" = "confirm"): Promise<void> {
    if (!session || !currentItem) {
      return;
    }
    const itemId = currentItem.id;
    armCaptureHoldAfterUserAction();
    try {
      setError(null);
      const response = await apiClient.confirmReceivingSessionItem(session.id, {
        item_id: itemId,
        decision,
        selected_candidate_index: currentItem.selected_candidate_index ?? 0,
      });
      setSession(response.session);
      setStatusMessage(decision === "confirm" ? "Confirmed current frame." : "Marked for review.");
      setError(null);
    } catch (err) {
      const recovered = await tryRecoverReceivingActionSession(session.id, itemId);
      if (recovered) {
        setSession(recovered);
        setStatusMessage(decision === "confirm" ? "Confirmed current frame." : "Marked for review.");
        setError(null);
        return;
      }
      setError(err instanceof ApiError ? err.message : "Unable to confirm the current item.");
    }
  }

  async function handleSkip(): Promise<void> {
    if (!session || !currentItem) {
      return;
    }
    const itemId = currentItem.id;
    armCaptureHoldAfterUserAction();
    try {
      setError(null);
      const response = await apiClient.skipReceivingSessionItem(session.id, {
        item_id: itemId,
        reason: "Live capture skip",
      });
      setSession(response.session);
      setStatusMessage("Skipped current frame.");
      setError(null);
    } catch (err) {
      const recovered = await tryRecoverReceivingActionSession(session.id, itemId);
      if (recovered) {
        setSession(recovered);
        setStatusMessage("Skipped current frame.");
        setError(null);
        return;
      }
      setError(err instanceof ApiError ? err.message : "Unable to skip the current item.");
    }
  }

  function handleReviewSessionUpdate(updated: ReceivingSessionDetailRead): void {
    setSession(updated);
  }

  function handleReviewModalClose(action: RecognitionReviewCloseAction): void {
    const itemId = pinnedReviewItemId ?? currentItem?.id ?? null;
    setManualReviewItemId(null);
    setPaused(pausedBeforeReviewRef.current);
    if (action === "accept") {
      armCaptureHoldAfterUserAction();
      setStatusMessage("Accepted match.");
      return;
    }
    if (itemId != null) {
      setDismissedReviewIds((prev) => (prev.includes(itemId) ? prev : [...prev, itemId]));
    }
    setStatusMessage("Review canceled. Confirm or skip this capture to continue.");
  }

  function handleOpenReview(): void {
    if (currentItem) {
      setManualReviewItemId(currentItem.id);
    }
  }

  useEffect(() => {
    if (!keyboardShortcuts) {
      return;
    }
    const handler = (event: KeyboardEvent): void => {
      if (reviewModalOpenRef.current || isLiveCaptureKeyboardTarget(event.target)) {
        return;
      }
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
        handleOpenReview();
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
              data-testid="live-capture-new-session"
              onClick={() => void startNewSession()}
              disabled={loading}
              className="rounded-full border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 disabled:opacity-50"
            >
              New session
            </button>
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
            <div ref={cameraViewportRef} className="relative aspect-[4/3] overflow-hidden rounded-[1.5rem] bg-slate-950">
              <CameraFeed
                videoRef={videoRef}
                deviceId={deviceId}
                mirrored={mirrored}
                className="h-full w-full"
                onError={handleCameraError}
                onStreamReady={handleStreamReady}
              />
              <ScannerFramingGuide
                overlayStyle={guideOverlayStyle}
                status={framingGuideStatus}
                hidden={paused || Boolean(cameraError) || !cameraReady}
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
            onReview={handleOpenReview}
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

      {reviewModalOpen && session && reviewItem ? (
        <RecognitionReviewModal
          open={reviewModalOpen}
          sessionId={session.id}
          item={reviewItem}
          capturedFrameUrl={capturedFrameUrl}
          onSessionUpdate={handleReviewSessionUpdate}
          onClose={handleReviewModalClose}
        />
      ) : null}
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
