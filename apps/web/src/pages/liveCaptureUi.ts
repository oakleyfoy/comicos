import type { ReceivingSessionItemRead } from "../api/client";

export const STABLE_FRAME_THRESHOLD = 3;

export function formatCaptureMode(source: "WEBCAM" | "MOBILE_CAMERA"): string {
  return source;
}

export function formatCaptureModeLabel(source: "WEBCAM" | "MOBILE_CAMERA"): string {
  if (source === "WEBCAM") {
    return "Webcam (desktop)";
  }
  return "Mobile camera";
}

export function formatDeviceOptionLabel(device: MediaDeviceInfo, index: number): string {
  const name = device.label?.trim() || `Camera ${index + 1}`;
  const shortId = device.deviceId ? device.deviceId.slice(0, 8) : "unknown";
  if (device.label?.trim()) {
    return `${name}`;
  }
  return `${name} (${shortId})`;
}

export function resolveActiveCameraName(
  devices: MediaDeviceInfo[],
  deviceId: string | null,
): string {
  if (!deviceId) {
    return "Default camera";
  }
  const match = devices.find((device) => device.deviceId === deviceId);
  if (match?.label?.trim()) {
    return match.label.trim();
  }
  if (match) {
    return `Camera ${match.deviceId.slice(0, 8)}`;
  }
  return "Selected camera";
}

export function friendlyCameraError(error: unknown): string {
  if (error instanceof DOMException) {
    if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
      return "Camera permission was denied. Allow camera access in your browser settings, then reload this page.";
    }
    if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
      return "No camera was found on this device.";
    }
    if (error.name === "NotReadableError") {
      return "Camera is in use by another app. Close other apps using the camera and try again.";
    }
    if (error.name === "OverconstrainedError") {
      return "That camera is unavailable. Choose a different camera from the list.";
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Unable to access the camera. Check permissions and try again.";
}

export type LiveCapturePhase =
  | "starting_session"
  | "paused"
  | "camera_error"
  | "camera_initializing"
  | "camera_ready"
  | "waiting_stable_frame"
  | "recognizing"
  | "ready_to_confirm";

export function liveCapturePhaseLabel(phase: LiveCapturePhase): string {
  switch (phase) {
    case "starting_session":
      return "Starting session…";
    case "paused":
      return "Paused";
    case "camera_error":
      return "Camera unavailable";
    case "camera_initializing":
      return "Camera initializing…";
    case "camera_ready":
      return "Camera ready";
    case "waiting_stable_frame":
      return "Waiting for stable frame";
    case "recognizing":
      return "Recognizing";
    case "ready_to_confirm":
      return "Ready to confirm";
    default:
      return "Camera ready";
  }
}

export function resolveLiveCapturePhase(input: {
  loading: boolean;
  paused: boolean;
  cameraError: string | null;
  cameraReady: boolean;
  recognizing: boolean;
  stableCount: number;
  currentItem: ReceivingSessionItemRead | null;
}): LiveCapturePhase {
  if (input.loading) {
    return "starting_session";
  }
  if (input.paused) {
    return "paused";
  }
  if (input.cameraError) {
    return "camera_error";
  }
  if (!input.cameraReady) {
    return "camera_initializing";
  }
  if (input.recognizing) {
    return "recognizing";
  }
  if (input.currentItem && input.currentItem.status !== "CONFIRMED" && input.currentItem.status !== "SKIPPED") {
    return "ready_to_confirm";
  }
  if (input.stableCount < STABLE_FRAME_THRESHOLD) {
    return "waiting_stable_frame";
  }
  return "camera_ready";
}

export function formatSessionLabel(sessionId: number | null | undefined): string {
  if (typeof sessionId !== "number") {
    return "Session pending…";
  }
  return `Session #${sessionId}`;
}

export function resolveLastFrameTimestamp(
  items: ReceivingSessionItemRead[],
  fallbackIso: string | null,
): string | null {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index];
    const candidate =
      item.capture_completed_at ?? item.uploaded_at ?? item.recognized_at ?? item.created_at;
    if (candidate) {
      return candidate;
    }
  }
  return fallbackIso;
}

export function formatLastFrameDisplay(iso: string | null): string {
  if (!iso) {
    return "No frames yet";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "No frames yet";
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}
