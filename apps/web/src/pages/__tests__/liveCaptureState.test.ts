import { describe, expect, it } from "vitest";

import { advanceStableFrameTracker, createStableFrameTracker, hasPendingReceivingItem, isCaptureHoldActive, nextCaptureHoldUntil, receivingActionItemFinalized, shouldIgnoreCaptureFailure, shouldSurfaceCaptureFailure, shouldSuppressDuplicateFingerprint } from "../liveCaptureState";

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

    const repeat = advanceStableFrameTracker(accepted.tracker, "frame-a", 3);
    expect(repeat.accepted).toBe(false);
    expect(repeat.tracker.sameCount).toBe(4);
  });

  it("suppresses duplicate fingerprints already seen", () => {
    expect(shouldSuppressDuplicateFingerprint(new Set(["frame-a"]), "frame-a")).toBe(true);
    expect(shouldSuppressDuplicateFingerprint(new Set(["frame-a"]), "frame-b")).toBe(false);
  });

  it("detects pending receiving items awaiting confirm or skip", () => {
    expect(hasPendingReceivingItem([{ status: "SKIPPED" }, { status: "CONFIRMED" }])).toBe(false);
    expect(hasPendingReceivingItem([{ status: "UNKNOWN" }])).toBe(true);
  });

  it("applies post-action capture hold and failure surfacing rules", () => {
    const holdUntil = nextCaptureHoldUntil(1000, 3000);
    expect(isCaptureHoldActive(holdUntil, 2000)).toBe(true);
    expect(isCaptureHoldActive(holdUntil, 4000)).toBe(false);
    expect(shouldIgnoreCaptureFailure(1, 2)).toBe(true);
    expect(shouldIgnoreCaptureFailure(2, 2)).toBe(false);
    expect(shouldSurfaceCaptureFailure([{ status: "VERIFIED" }])).toBe(true);
    expect(shouldSurfaceCaptureFailure([{ status: "CONFIRMED" }])).toBe(false);
    expect(receivingActionItemFinalized([{ id: 5, status: "SKIPPED" }], 5)).toBe(true);
    expect(receivingActionItemFinalized([{ id: 5, status: "VERIFIED" }], 5)).toBe(false);
  });
});
