import { describe, expect, it } from "vitest";

import {
  averageHashFromRgba,
  fingerprintsSimilar,
  hammingDistanceHex,
} from "../liveCaptureFingerprint";
import { advanceStableFrameTracker, createStableFrameTracker } from "../liveCaptureState";

describe("liveCaptureFingerprint", () => {
  it("treats near-identical hashes as similar", () => {
    expect(fingerprintsSimilar("abcd1234", "abcd1234")).toBe(true);
    expect(hammingDistanceHex("0000", "0001")).toBe(1);
    expect(fingerprintsSimilar("0000", "0001", 1)).toBe(true);
    expect(fingerprintsSimilar("0000", "ffff", 1)).toBe(false);
  });

  it("builds a 16-char hex aHash from 8x8 rgba", () => {
    const data = new Uint8ClampedArray(8 * 8 * 4);
    for (let index = 0; index < data.length; index += 4) {
      data[index] = 200;
      data[index + 1] = 200;
      data[index + 2] = 200;
    }
    const hash = averageHashFromRgba(data, 8, 8);
    expect(hash).toHaveLength(16);
  });
});

describe("stable frame with fuzzy fingerprints", () => {
  it("increments stable count across similar hashes", () => {
    let tracker = createStableFrameTracker();
    const similar: typeof fingerprintsSimilar = (a, b) => fingerprintsSimilar(a, b, 2);

    ({ tracker } = advanceStableFrameTracker(tracker, "aaaa0000", 3, similar));
    expect(tracker.sameCount).toBe(1);

    ({ tracker } = advanceStableFrameTracker(tracker, "aaaa0001", 3, similar));
    expect(tracker.sameCount).toBe(2);

    const result = advanceStableFrameTracker(tracker, "aaaa0000", 3, similar);
    expect(result.accepted).toBe(true);
    expect(result.tracker.sameCount).toBe(3);
  });
});
