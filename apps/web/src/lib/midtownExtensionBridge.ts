export const MIDTOWN_EXTENSION_READY_EVENT = "comicos_midtown_extension_ready";
export const MIDTOWN_EXTENSION_PING_EVENT = "comicos_midtown_extension_ping";
export const MIDTOWN_EXTENSION_CAPTURE_REQUEST_EVENT = "comicos_midtown_capture_request";
export const MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT = "comicos_midtown_capture_result";
export const MIDTOWN_EXTENSION_CAPTURE_ERROR_EVENT = "comicos_midtown_capture_error";

export interface MidtownExtensionCaptureRequest {
  accountId: number;
  syncRunId: number;
  captureToken: string;
  appOrigin: string;
}

export interface MidtownExtensionDetailPageCapture {
  detail_url: string;
  html: string;
  retailer_order_number?: string | null;
  fallback_order_number?: string | null;
}

export interface MidtownExtensionCaptureResult extends MidtownExtensionCaptureRequest {
  historyHtml: string;
  detailPages: MidtownExtensionDetailPageCapture[];
}

export interface MidtownExtensionCaptureError {
  message: string;
  accountId?: number;
  syncRunId?: number;
}

export function getMidtownExtensionInstallUrl(): string | null {
  const configured = import.meta.env.VITE_MIDTOWN_EXTENSION_INSTALL_URL;
  return typeof configured === "string" && configured.trim().length > 0
    ? configured.trim()
    : null;
}

export function isMidtownExtensionCaptureResult(data: unknown): data is {
  type: typeof MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT;
  accountId: number;
  syncRunId: number;
  captureToken: string;
  historyHtml: string;
  detailPages: MidtownExtensionDetailPageCapture[];
} {
  if (!data || typeof data !== "object") {
    return false;
  }
  const record = data as Record<string, unknown>;
  return (
    record.type === MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT &&
    typeof record.accountId === "number" &&
    typeof record.syncRunId === "number" &&
    typeof record.captureToken === "string" &&
    typeof record.historyHtml === "string" &&
    Array.isArray(record.detailPages)
  );
}

export function isMidtownExtensionCaptureError(data: unknown): data is {
  type: typeof MIDTOWN_EXTENSION_CAPTURE_ERROR_EVENT;
  message: string;
  accountId?: number;
  syncRunId?: number;
} {
  if (!data || typeof data !== "object") {
    return false;
  }
  const record = data as Record<string, unknown>;
  return record.type === MIDTOWN_EXTENSION_CAPTURE_ERROR_EVENT && typeof record.message === "string";
}
