export const MIDTOWN_EXTENSION_READY_EVENT = "comicos_midtown_extension_ready";
export const MIDTOWN_EXTENSION_PING_EVENT = "comicos_midtown_extension_ping";
export const MIDTOWN_EXTENSION_CAPTURE_REQUEST_EVENT = "comicos_midtown_capture_request";
export const MIDTOWN_EXTENSION_CAPTURE_RESULT_EVENT = "comicos_midtown_capture_result";
export const MIDTOWN_EXTENSION_CAPTURE_ERROR_EVENT = "comicos_midtown_capture_error";
export const MIDTOWN_EXTENSION_STATUS_EVENT = "comicos_midtown_extension_status";

export interface MidtownExtensionCaptureRequest {
  accountId: number;
  syncRunId: number;
  captureToken: string;
  appOrigin: string;
}

export interface MidtownExtensionCaptureDiagnostics extends Record<string, unknown> {
  current_url: string;
  ready_state: string;
  html_length: number;
  text_length: number;
  body_inner_html_length: number;
  body_inner_text_length: number;
  image_count: number;
  product_link_count: number;
  visible_order_item_block_count: number;
  items_detected_client_side: number;
  each_match_count: number;
  qty_match_count: number;
  status_match_count: number;
  scroll_height: number;
  scroll_position: number;
}

export interface MidtownExtensionDetailPageCapture {
  detail_url: string;
  html: string;
  retailer_order_number?: string | null;
  fallback_order_number?: string | null;
  capture_diagnostics?: MidtownExtensionCaptureDiagnostics | null;
}

export interface MidtownExtensionCaptureResult {
  accountId: number;
  syncRunId: number;
  captureToken: string;
  appOrigin?: string;
  historyHtml: string;
  detailPages: MidtownExtensionDetailPageCapture[];
}

export interface MidtownExtensionCaptureError {
  message: string;
  accountId?: number;
  syncRunId?: number;
}

export interface MidtownExtensionStatusMessage {
  stage: "extension_connected" | "midtown_page_detected" | "dom_read_success";
  message: string;
  accountId?: number;
  syncRunId?: number;
  captureToken?: string;
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

export function isMidtownExtensionStatusMessage(data: unknown): data is {
  type: typeof MIDTOWN_EXTENSION_STATUS_EVENT;
  stage: MidtownExtensionStatusMessage["stage"];
  message: string;
  accountId?: number;
  syncRunId?: number;
  captureToken?: string;
} {
  if (!data || typeof data !== "object") {
    return false;
  }
  const record = data as Record<string, unknown>;
  return (
    record.type === MIDTOWN_EXTENSION_STATUS_EVENT &&
    (record.stage === "extension_connected" ||
      record.stage === "midtown_page_detected" ||
      record.stage === "dom_read_success") &&
    typeof record.message === "string"
  );
}
