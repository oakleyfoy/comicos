import { describe, expect, it } from "vitest";

import {
  analyzeComicPresenceFromRgba,
  computeGuideRect,
  mapGuideRectToOverlayStyle,
  resolveFramingGuideStatus,
} from "../liveCaptureFraming";

function variedRgba(size: number): Uint8ClampedArray {
  const data = new Uint8ClampedArray(size * size * 4);
  for (let index = 0; index < data.length; index += 4) {
    data[index] = 40 + (index % 80);
    data[index + 1] = 60 + (index % 70);
    data[index + 2] = 50 + (index % 90);
    data[index + 3] = 255;
  }
  return data;
}

describe("liveCaptureFraming", () => {
  it("computes a centered portrait guide with comic aspect ratio", () => {
    const rect = computeGuideRect(1200, 1800);
    expect(rect.width / rect.height).toBeCloseTo(6.625 / 10.125, 3);
    expect(rect.x + rect.width).toBeLessThanOrEqual(1200);
    expect(rect.y + rect.height).toBeLessThanOrEqual(1800);
    expect(rect.x).toBeGreaterThan(0);
    expect(rect.y).toBeGreaterThan(0);
  });

  it("detects comic-like texture in guide samples", () => {
    const presence = analyzeComicPresenceFromRgba(variedRgba(32));
    expect(presence.detected).toBe(true);
  });

  it("rejects flat empty guide samples", () => {
    const flat = new Uint8ClampedArray(32 * 32 * 4).fill(1);
    expect(analyzeComicPresenceFromRgba(flat).detected).toBe(false);
  });

  it("maps guide status from detection and stability", () => {
    expect(resolveFramingGuideStatus(false, 0, 3)).toBe("none");
    expect(resolveFramingGuideStatus(true, 1, 3)).toBe("unstable");
    expect(resolveFramingGuideStatus(true, 3, 3)).toBe("ready");
  });

  it("maps overlay coordinates for object-cover layout", () => {
    const rect = computeGuideRect(1200, 1800);
    const style = mapGuideRectToOverlayStyle(1200, 1800, 400, 300, rect, false);
    expect(style.left).toMatch(/%$/);
    expect(style.width).toMatch(/%$/);
  });
});
