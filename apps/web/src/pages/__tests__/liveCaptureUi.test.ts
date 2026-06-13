import { describe, expect, it } from "vitest";

import {
  friendlyCameraError,
  formatSessionLabel,
  liveCapturePhaseLabel,
  resolveActiveCameraName,
  resolveLiveCapturePhase,
  STABLE_FRAME_THRESHOLD,
} from "../liveCaptureUi";

describe("liveCaptureUi", () => {
  it("maps permission errors to friendly camera messages", () => {
    expect(friendlyCameraError(new DOMException("denied", "NotAllowedError"))).toMatch(/permission/i);
    expect(friendlyCameraError(new DOMException("busy", "NotReadableError"))).toMatch(/in use/i);
  });

  it("resolves active camera name from device list", () => {
    const devices = [
      { kind: "videoinput", deviceId: "abc", label: "Surface Camera Front" } as MediaDeviceInfo,
    ];
    expect(resolveActiveCameraName(devices, "abc")).toBe("Surface Camera Front");
    expect(resolveActiveCameraName(devices, null)).toBe("Default camera");
  });

  it("derives live capture phase for confirm-ready state", () => {
    const phase = resolveLiveCapturePhase({
      loading: false,
      paused: false,
      cameraError: null,
      cameraReady: true,
      recognizing: false,
      stableCount: STABLE_FRAME_THRESHOLD,
      currentItem: {
        id: 1,
        status: "VERIFIED",
      } as never,
    });
    expect(liveCapturePhaseLabel(phase)).toBe("Ready to confirm");
  });

  it("formats session label", () => {
    expect(formatSessionLabel(42)).toBe("Session #42");
  });
});
