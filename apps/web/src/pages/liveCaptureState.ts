export interface StableFrameTracker {
  lastFingerprint: string | null;
  sameCount: number;
  paused: boolean;
}

export function createStableFrameTracker(): StableFrameTracker {
  return {
    lastFingerprint: null,
    sameCount: 0,
    paused: false,
  };
}

export type FingerprintSimilarity = (previous: string, current: string) => boolean;

export function advanceStableFrameTracker(
  tracker: StableFrameTracker,
  fingerprint: string,
  threshold = 3,
  isSimilar: FingerprintSimilarity = (previous, current) => previous === current,
): { tracker: StableFrameTracker; accepted: boolean; stableIncremented: boolean } {
  if (tracker.paused) {
    return { tracker, accepted: false, stableIncremented: false };
  }

  const priorCount = tracker.sameCount;
  let sameCount = 1;
  let stableIncremented = false;
  if (tracker.lastFingerprint && isSimilar(tracker.lastFingerprint, fingerprint)) {
    sameCount = tracker.sameCount + 1;
    stableIncremented = sameCount > priorCount;
  }

  // Fire once when the streak crosses the threshold (not on every subsequent tick).
  const accepted = sameCount >= threshold && priorCount < threshold;
  return {
    tracker: {
      ...tracker,
      lastFingerprint: fingerprint,
      sameCount,
    },
    accepted,
    stableIncremented,
  };
}

export function shouldSuppressDuplicateFingerprint(
  recentFingerprints: ReadonlySet<string>,
  fingerprint: string,
): boolean {
  return recentFingerprints.has(fingerprint);
}

export function hasPendingReceivingItem(
  items: ReadonlyArray<{ status: string }> | undefined,
): boolean {
  return (items ?? []).some((item) => item.status !== "CONFIRMED" && item.status !== "SKIPPED");
}

/** Pause auto-capture briefly after confirm/skip so the next frame does not race the action. */
export const LIVE_CAPTURE_POST_ACTION_HOLD_MS = 3000;

export function nextCaptureHoldUntil(
  nowMs: number,
  holdMs: number = LIVE_CAPTURE_POST_ACTION_HOLD_MS,
): number {
  return nowMs + holdMs;
}

export function isCaptureHoldActive(holdUntilMs: number, nowMs: number): boolean {
  return nowMs < holdUntilMs;
}

export function shouldIgnoreCaptureFailure(actionEpochAtStart: number, actionEpoch: number): boolean {
  return actionEpochAtStart !== actionEpoch;
}

/** Background uploads after an item is resolved should not use the fatal error banner. */
export function shouldSurfaceCaptureFailure(
  items: ReadonlyArray<{ status: string }> | undefined,
): boolean {
  return hasPendingReceivingItem(items);
}

export function receivingActionItemFinalized(
  items: ReadonlyArray<{ id: number; status: string }>,
  itemId: number,
): boolean {
  const item = items.find((row) => row.id === itemId);
  return Boolean(item && (item.status === "CONFIRMED" || item.status === "SKIPPED"));
}

export function shouldStartLiveCaptureUpload(input: {
  uploadInFlight: boolean;
  holdActive: boolean;
  hasPendingItem: boolean;
}): boolean {
  if (input.uploadInFlight) {
    return false;
  }
  if (input.holdActive) {
    return false;
  }
  if (input.hasPendingItem) {
    return false;
  }
  return true;
}
