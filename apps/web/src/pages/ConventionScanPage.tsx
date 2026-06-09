import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, apiClient, type InventorySummary, type P80CollectorScanResultRead } from "../api/client";
import { StatusBanner } from "../components/StatusBanner";
import { CameraFeed } from "../components/live-capture/CameraFeed";
import { RecognitionOverlay } from "../components/live-capture/RecognitionOverlay";
import { advanceStableFrameTracker, createStableFrameTracker, shouldSuppressDuplicateFingerprint } from "./liveCaptureState";

function fingerprintFrameFromVideo(video: HTMLVideoElement): string | null {
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

async function captureVideoFrame(video: HTMLVideoElement, fingerprint: string): Promise<File | null> {
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
  return new File([blob], `convention-${fingerprint}.jpg`, { type: "image/jpeg" });
}

function formatTitle(result: P80CollectorScanResultRead | null): string {
  const book = result?.identification.book;
  return book ? `${book.title} #${book.issue_number}` : "Awaiting scan";
}

export function ConventionScanPage(): JSX.Element {
  const videoRef = useRef<HTMLVideoElement>(null);
  const trackerRef = useRef(createStableFrameTracker());
  const recentFingerprintsRef = useRef<Set<string>>(new Set());
  const inFlightFingerprintRef = useRef<string | null>(null);
  const [result, setResult] = useState<P80CollectorScanResultRead | null>(null);
  const [inventorySummary, setInventorySummary] = useState<InventorySummary | null>(null);
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("Point the camera at a comic.");
  const [stableCount, setStableCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function loadSummary(): Promise<void> {
      try {
        const summary = await apiClient.getInventorySummary();
        if (!cancelled) {
          setInventorySummary(summary);
        }
      } catch {
        if (!cancelled) {
          setInventorySummary(null);
        }
      }
    }
    void loadSummary();
    return () => {
      cancelled = true;
    };
  }, []);

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
    const timer = window.setInterval(() => {
      const video = videoRef.current;
      if (!video || inFlightFingerprintRef.current) {
        return;
      }
      const fingerprint = fingerprintFrameFromVideo(video);
      if (!fingerprint) {
        return;
      }
      const next = advanceStableFrameTracker(trackerRef.current, fingerprint, 3);
      trackerRef.current = next.tracker;
      setStableCount(next.tracker.sameCount);
      if (!next.accepted || shouldSuppressDuplicateFingerprint(recentFingerprintsRef.current, fingerprint)) {
        return;
      }
      inFlightFingerprintRef.current = fingerprint;
      void (async () => {
        try {
          const file = await captureVideoFrame(video, fingerprint);
          if (!file) {
            return;
          }
          const identification = await apiClient.identifyComicFromImage(file);
          const manualEntry =
            identification.series && identification.issue_number
              ? `${identification.series} #${identification.issue_number}`
              : identification.series ?? identification.issue_number ?? undefined;
          const scan = await apiClient.collectorScan({
            manual_entry: manualEntry,
          });
          recentFingerprintsRef.current.add(fingerprint);
          setResult(scan);
          setStatusMessage(scan.action_card.action);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Unable to evaluate convention scan.");
        } finally {
          inFlightFingerprintRef.current = null;
        }
      })();
    }, 300);
    return () => window.clearInterval(timer);
  }, []);

  const ownership = result?.book_intelligence?.ownership;
  const fmv = result?.book_intelligence?.fmv;
  const recommendation = result?.book_intelligence?.recommendation;
  const collection = result?.collection_completion;

  const stats = useMemo(
    () => [
      { label: "Owned", value: String(ownership?.total_copies ?? inventorySummary?.total_copies ?? 0) },
      {
        label: "FMV",
        value: fmv?.authoritative_fmv != null ? `$${fmv.authoritative_fmv.toFixed(0)}` : "—",
      },
      { label: "Recommendation", value: recommendation?.recommendation ?? "—" },
      {
        label: "Collection",
        value:
          collection?.completion_percent != null
            ? `${Math.round(collection.completion_percent * 100)}%`
            : inventorySummary
              ? `${inventorySummary.in_hand_copies}/${inventorySummary.total_copies}`
              : "—",
      },
    ],
    [collection, fmv, inventorySummary, ownership, recommendation],
  );

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 px-4 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">P95-04 · Convention Scan</p>
            <h1 className="text-2xl font-semibold">Convention Scan</h1>
          </div>
          <Link to="/collector-assistant" className="text-sm text-slate-300 underline-offset-2 hover:underline">
            Collector assistant
          </Link>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(360px,0.9fr)]">
        <section className="space-y-4">
          {error ? <StatusBanner tone="error">{error}</StatusBanner> : null}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {stats.map((stat) => (
              <div key={stat.label} className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{stat.label}</p>
                <p className="mt-2 text-lg font-semibold">{stat.value}</p>
              </div>
            ))}
          </div>

          <div className="rounded-[2rem] border border-slate-800 bg-slate-900 p-3 shadow-2xl">
            <div className="relative aspect-[4/3] overflow-hidden rounded-[1.5rem] bg-slate-950">
              <CameraFeed
                videoRef={videoRef}
                deviceId={deviceId}
                className="h-full w-full"
                onError={(message) => setError(message)}
              />
              <RecognitionOverlay
                title={formatTitle(result)}
                subtitle={result?.action_card.action ?? "Convention-only evaluation"}
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
            <div className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-300">
              Stable frames: {stableCount}
            </div>
          </div>
        </section>

        <aside className="space-y-4">
          <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Ownership</p>
            <p className="mt-3 text-3xl font-semibold">{ownership?.total_copies ?? 0}</p>
            <p className="mt-1 text-sm text-slate-400">
              {ownership?.graded_copies ?? 0} graded · {ownership?.raw_copies ?? 0} raw
            </p>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">FMV</p>
            <p className="mt-3 text-3xl font-semibold">{fmv?.authoritative_fmv != null ? `$${fmv.authoritative_fmv.toFixed(0)}` : "—"}</p>
            <p className="mt-1 text-sm text-slate-400">
              {fmv?.confidence_score != null ? `Confidence ${Math.round(fmv.confidence_score * 100)}%` : "No FMV confidence yet"}
            </p>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Recommendation</p>
            <p className="mt-3 text-2xl font-semibold">{recommendation?.recommendation ?? "—"}</p>
            <p className="mt-1 text-sm text-slate-400">{recommendation?.rationale ?? "Convention scan is evaluation only."}</p>
          </div>

          <div className="rounded-3xl border border-slate-800 bg-slate-900 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Collection status</p>
            <p className="mt-3 text-2xl font-semibold">
              {collection?.label ?? `${inventorySummary?.in_hand_copies ?? 0}/${inventorySummary?.total_copies ?? 0}`}
            </p>
            <p className="mt-1 text-sm text-slate-400">
              {collection?.missing_issue_numbers?.length ? `${collection.missing_issue_numbers.length} missing issues` : "No gaps detected"}
            </p>
          </div>
        </aside>
      </main>
    </div>
  );
}
