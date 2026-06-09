import { describe, expect, it } from "vitest";

import { advanceStableFrameTracker, createStableFrameTracker, shouldSuppressDuplicateFingerprint } from "../liveCaptureState";

describe("liveCaptureState", () => {
  it("accepts a stable frame after three matching fingerprints", () => {
    let tracker = createStableFrameTracker();

    ({ tracker } = advanceStableFrameTracker(tracker, "frame-a", 3));
    expect(tracker.sameCount).toBe(1);

    ({ tracker } = advanceStableFrameTracker(tracker, "frame-a", 3));
    expect(tracker.sameCount).toBe(2);

    const accepted = advanceStableFrameTracker(tracker, "frame-a", 3);
    expect(accepted.accepted).toBe(true);
    expect(accepted.tracker.sameCount).toBe(3);
    expect(accepted.tracker.acceptedFingerprint).toBe("frame-a");
  });

  it("suppresses duplicate fingerprints already seen", () => {
    expect(shouldSuppressDuplicateFingerprint(new Set(["frame-a"]), "frame-a")).toBe(true);
    expect(shouldSuppressDuplicateFingerprint(new Set(["frame-a"]), "frame-b")).toBe(false);
  });
});
