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
