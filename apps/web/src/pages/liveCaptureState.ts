export interface StableFrameTracker {
  lastFingerprint: string | null;
  sameCount: number;
  acceptedFingerprint: string | null;
  paused: boolean;
}

export function createStableFrameTracker(): StableFrameTracker {
  return {
    lastFingerprint: null,
    sameCount: 0,
    acceptedFingerprint: null,
    paused: false,
  };
}

export function advanceStableFrameTracker(
  tracker: StableFrameTracker,
  fingerprint: string,
  threshold = 3,
): { tracker: StableFrameTracker; accepted: boolean } {
  if (tracker.paused) {
    return { tracker, accepted: false };
  }

  let sameCount = 1;
  if (tracker.lastFingerprint === fingerprint) {
    sameCount = tracker.sameCount + 1;
  }

  const accepted = sameCount >= threshold && tracker.acceptedFingerprint !== fingerprint;
  return {
    tracker: {
      ...tracker,
      lastFingerprint: fingerprint,
      sameCount,
      acceptedFingerprint: accepted ? fingerprint : tracker.acceptedFingerprint,
    },
    accepted,
  };
}

export function shouldSuppressDuplicateFingerprint(
  recentFingerprints: ReadonlySet<string>,
  fingerprint: string,
): boolean {
  return recentFingerprints.has(fingerprint);
}
