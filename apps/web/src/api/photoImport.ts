import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class PhotoImportApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "PhotoImportApiError";
    this.status = status;
  }
}

async function requestPhotoImport<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = `${path} failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new PhotoImportApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export type PhotoImportSession = {
  id: number;
  session_token: string;
  status: string;
  created_at: string;
  expires_at: string;
  last_seen_at: string | null;
  source_device: string | null;
  confirmed_count: number;
  uploaded_photo_count: number;
  detected_book_count: number;
  capture_mode: "single_comic" | "group";
  mobile_url: string;
  desktop_review_url: string;
  vision_sandbox?: boolean;
};

export type PhotoImportCatalogAlternate = {
  catalog_issue_id: number;
  series: string | null;
  issue_number: string | null;
  publisher: string | null;
  cover_url: string | null;
  confidence: number | null;
};

export type PhotoImportVisionRead = {
  id: number;
  session_id: number;
  image_id: number;
  detection_index?: number;
  publisher: string | null;
  series: string | null;
  issue_number: string | null;
  issue_title: string | null;
  variant_description: string | null;
  year: string | null;
  cover_date: string | null;
  barcode: string | null;
  confidence: number | null;
  reasoning: string | null;
  possible_alternates?: string[] | null;
  raw_response: Record<string, unknown> | null;
  is_correct: boolean | null;
  feedback_notes: string | null;
  added_to_inventory?: boolean;
  catalog_issue_id?: number | null;
  catalog_variant_id?: number | null;
  catalog_cover_url?: string | null;
  match_method?: string | null;
  match_confidence?: number | null;
  catalog_series?: string | null;
  catalog_issue_number?: string | null;
  catalog_publisher?: string | null;
  catalog_alternates?: PhotoImportCatalogAlternate[];
  created_at: string;
};

export type PhotoImportAddAllResult = {
  added_count: number;
  total_copies: number;
  results: PhotoImportVisionReadInventoryResult[];
};

export type PhotoImportVisionReadUpdate = {
  publisher?: string | null;
  series?: string | null;
  issue_number?: string | null;
  issue_title?: string | null;
  variant_description?: string | null;
  year?: string | null;
  cover_date?: string | null;
  barcode?: string | null;
};

export type PhotoImportVisionReadInventoryResult = {
  vision_read: PhotoImportVisionRead;
  acquisition_id: number | null;
  created_count: number;
  inventory_copy_ids: number[];
};

export type PhotoImportVisionSandboxMetrics = {
  total_reads: number;
  correct_reads: number;
  incorrect_reads: number;
  pending_feedback: number;
  accuracy_percent: number;
  publisher_filled_percent?: number;
  series_filled_percent?: number;
  issue_number_filled_percent?: number;
  average_confidence?: number;
  top_uncertain_reads?: Array<Record<string, unknown>>;
  latest_incorrect_reads?: Array<Record<string, unknown>>;
  publisher_accuracy: number;
  series_accuracy: number;
  issue_accuracy: number;
  top_failures: Array<Record<string, unknown>>;
  most_misidentified_series: Array<{ series: string; count: number }>;
  most_misidentified_publishers: Array<{ publisher: string; count: number }>;
};

export type PhotoImportCaptureMode = "single_comic" | "group";

/** Desktop folder pipeline + phone drop box (scan QR once). */
export const PHOTO_IMPORT_FOLDER_SOURCE = "folder_import";

/** Desktop GPT review route (optional exceptions-only mode for folder import). */
export function photoImportReviewPath(
  sessionToken: string,
  options?: { exceptionsOnly?: boolean; fromFolder?: boolean },
): string {
  const params = new URLSearchParams();
  if (options?.exceptionsOnly) params.set("exceptions", "1");
  if (options?.fromFolder) params.set("from", "folder");
  const query = params.toString();
  return `/add-comics/photo/session/${encodeURIComponent(sessionToken)}${query ? `?${query}` : ""}`;
}

export function isPhotoImportVisionReadException(read: PhotoImportVisionRead): boolean {
  return !read.added_to_inventory;
}

export type PhotoImportFolderQueueStatus = {
  pending_uploads: number;
  processing: number;
  processed: number;
  failed: number;
  vision_reads: number;
  pending_inventory: number;
  queue_empty: boolean;
};

export type PhotoImportProcessPendingResponse = {
  started_image_ids: number[];
  queue: PhotoImportFolderQueueStatus;
};

export type PhotoImportImage = {
  id: number;
  session_id: number;
  original_filename: string;
  mime_type: string;
  file_size: number;
  width: number | null;
  height: number | null;
  status: string;
  created_at: string;
};

export type PhotoImportImageVerification = {
  image_id: number;
  image_status: string;
  reads: PhotoImportVisionRead[];
};

export type PhotoImportVisionStreamHandlers = {
  onStatus?: (data: { phase?: string; vision_mode?: string; message?: string }) => void;
  onToken?: (text: string) => void;
  onDone?: (verification: PhotoImportImageVerification) => void;
  onError?: (message: string) => void;
};

export type PhotoImportCandidate = {
  id: number;
  detected_book_id: number;
  catalog_issue_id: number;
  variant_id: number | null;
  publisher: string | null;
  series: string | null;
  issue_number: string | null;
  variant_name: string | null;
  cover_url: string | null;
  thumbnail_url: string | null;
  release_date: string | null;
  match_score: number;
  match_reason: string | null;
  matched_on: string | null;
  rank: number;
  base_text_score?: number | null;
  cover_similarity_score?: number | null;
  fingerprint_score?: number | null;
  barcode_score?: number | null;
  final_score?: number | null;
  visual_score_status?: string | null;
  visual_match_label?: string | null;
};

export type PhotoImportDetectedBook = {
  id: number;
  session_id: number;
  image_id: number;
  crop_path: string | null;
  crop_image_url: string | null;
  display_image_url: string | null;
  source_image_url: string | null;
  recognition_source: string | null;
  display_crop: boolean;
  status: string;
  recognition_status: string;
  candidate_count: number;
  selected_catalog_issue_id: number | null;
  confidence: number;
  ai_series: string | null;
  ai_issue_number: string | null;
  ai_publisher: string | null;
  ai_subtitle_guess: string | null;
  ai_variant_hint: string | null;
  ai_variant_guess: string | null;
  ai_cover_year: string | null;
  ai_visible_title_text: string | null;
  ai_visible_issue_text: string | null;
  ai_visible_publisher_text: string | null;
  ai_visible_character_text: string | null;
  ai_uncertainty_reason: string | null;
  ai_alternate_titles: string[] | null;
  ai_confidence: number | null;
  ai_reason: string | null;
  can_confirm: boolean;
  needs_match: boolean;
  review_status: string;
  best_candidate: PhotoImportCandidate | null;
  recognition_mode?: string | null;
  ai_barcode?: string | null;
  verification_reason?: string | null;
  vision_identification_label?: string | null;
  catalog_verification_status?: string | null;
  catalog_verification_label?: string | null;
  catalog_disagreement_reason?: string | null;
};

export type PhotoImportCandidatesDebugResponse = {
  detection: PhotoImportDetectedBook;
  candidates: PhotoImportCandidate[];
  selected_candidate: PhotoImportCandidate | null;
  debug: {
    search_terms_used: string[];
    candidate_count: number;
    best_match_score: number;
    match_input: Record<string, unknown>;
  };
};

export function createPhotoImportSession(
  sourceDevice?: string,
  captureMode?: PhotoImportCaptureMode,
): Promise<PhotoImportSession> {
  return requestPhotoImport("/api/v1/photo-import/sessions", {
    method: "POST",
    body: JSON.stringify({
      ...(sourceDevice ? { source_device: sourceDevice } : {}),
      ...(captureMode ? { capture_mode: captureMode } : {}),
    }),
  });
}

export function getPhotoImportSession(token: string): Promise<PhotoImportSession> {
  return requestPhotoImport(`/api/v1/photo-import/sessions/${encodeURIComponent(token)}`);
}

export function getPhotoImportFolderQueue(token: string): Promise<PhotoImportFolderQueueStatus> {
  return requestPhotoImport(
    `/api/v1/photo-import/sessions/${encodeURIComponent(token)}/folder-queue`,
  );
}

export function processPhotoImportFolderPending(
  token: string,
  limit = 2,
): Promise<PhotoImportProcessPendingResponse> {
  return requestPhotoImport(
    `/api/v1/photo-import/sessions/${encodeURIComponent(token)}/folder-process-pending?limit=${limit}`,
    { method: "POST" },
  );
}

export function resetPhotoImportFolderVision(
  token: string,
): Promise<{ images_reset: number; queue: PhotoImportFolderQueueStatus }> {
  return requestPhotoImport(
    `/api/v1/photo-import/sessions/${encodeURIComponent(token)}/folder-reset-vision`,
    { method: "POST" },
  );
}

export function heartbeatPhotoImportSession(
  token: string,
  options?: { sourceDevice?: string; captureMode?: PhotoImportCaptureMode },
): Promise<PhotoImportSession> {
  const body: { source_device?: string; capture_mode?: PhotoImportCaptureMode } = {};
  if (options?.sourceDevice) body.source_device = options.sourceDevice;
  if (options?.captureMode) body.capture_mode = options.captureMode;
  return requestPhotoImport(`/api/v1/photo-import/sessions/${encodeURIComponent(token)}/heartbeat`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listPhotoImportDetections(token: string): Promise<PhotoImportDetectedBook[]> {
  return requestPhotoImport(`/api/v1/photo-import/sessions/${encodeURIComponent(token)}/detections`);
}

export async function uploadPhotoImportImages(token: string, files: File[]): Promise<PhotoImportImage[]> {
  const form = new FormData();
  for (const file of files) {
    form.append("images", file);
  }
  return requestPhotoImport(`/api/v1/photo-import/sessions/${encodeURIComponent(token)}/images`, {
    method: "POST",
    body: form,
  });
}

export function confirmPhotoImportSession(
  token: string,
  items: { detected_book_id: number; catalog_issue_id: number; quantity?: number }[],
): Promise<{ acquisition_id: number; inventory_copy_ids: number[]; confirmed_count: number }> {
  return requestPhotoImport(`/api/v1/photo-import/sessions/${encodeURIComponent(token)}/confirm`, {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

export function getPhotoImportDetectionCandidates(
  detectionId: number,
): Promise<PhotoImportCandidatesDebugResponse> {
  return requestPhotoImport(`/api/v1/photo-import/detections/${detectionId}/candidates`);
}

export function selectPhotoImportCandidate(
  detectionId: number,
  candidateId: number,
): Promise<PhotoImportDetectedBook> {
  return requestPhotoImport(`/api/v1/photo-import/detections/${detectionId}/select-candidate`, {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export function rejectPhotoImportDetection(detectionId: number): Promise<PhotoImportDetectedBook> {
  return requestPhotoImport(`/api/v1/photo-import/detections/${detectionId}/reject`, { method: "POST" });
}

export async function fetchDetectionCropObjectUrl(detectionId: number): Promise<string | null> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const res = await fetch(`${API_BASE}/api/v1/photo-import/detections/${detectionId}/crop-image`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) return null;
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export function mobilePhotoImportUrl(token: string): string {
  const base = window.location.origin;
  return `${base}/photo-import/mobile/${encodeURIComponent(token)}`;
}

export function qrCodeUrlForLink(link: string): string {
  return `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(link)}`;
}

export async function listSessionVisionReads(sessionToken: string): Promise<PhotoImportVisionRead[]> {
  return requestPhotoImport(
    `/api/v1/photo-import/sessions/${encodeURIComponent(sessionToken)}/vision-reads`,
  );
}

export async function getVisionReadForImage(
  imageId: number,
  sessionToken: string,
): Promise<PhotoImportVisionRead> {
  const q = new URLSearchParams({ session_token: sessionToken });
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${imageId}?${q.toString()}`);
}

export async function submitVisionReadFeedback(
  readId: number,
  payload: { is_correct: boolean; feedback_notes?: string },
): Promise<PhotoImportVisionRead> {
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${readId}/feedback`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateVisionRead(
  readId: number,
  payload: PhotoImportVisionReadUpdate,
): Promise<PhotoImportVisionRead> {
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${readId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function addVisionReadToInventory(
  readId: number,
): Promise<PhotoImportVisionReadInventoryResult> {
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${readId}/add-to-inventory`, {
    method: "POST",
  });
}

export async function rereadVisionRead(
  readId: number,
  mode: "quick" | "accurate" = "accurate",
): Promise<PhotoImportVisionRead[]> {
  const q = new URLSearchParams({ mode });
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${readId}/reread?${q.toString()}`, {
    method: "POST",
  });
}

export async function rematchVisionRead(readId: number): Promise<PhotoImportVisionRead> {
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${readId}/rematch`, {
    method: "POST",
  });
}

export async function catalogMatchVisionRead(readId: number): Promise<PhotoImportVisionRead> {
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${readId}/catalog-match`, {
    method: "POST",
  });
}

export async function validateComicvineOnDemand(readId: number): Promise<PhotoImportVisionRead> {
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${readId}/validate-ondemand`, {
    method: "POST",
  });
}

export async function cancelVisionReadCatalogMatch(readId: number): Promise<PhotoImportVisionRead> {
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${readId}/cancel-catalog-match`, {
    method: "POST",
  });
}

export async function catalogMatchVisionReads(
  sessionToken: string,
  readIds: number[],
): Promise<PhotoImportVisionRead[]> {
  return requestPhotoImport(
    `/api/v1/photo-import/sessions/${encodeURIComponent(sessionToken)}/catalog-match`,
    {
      method: "POST",
      body: JSON.stringify({ read_ids: readIds }),
    },
  );
}

export async function getPhotoImportImageVerification(
  sessionToken: string,
  imageId: number,
): Promise<PhotoImportImageVerification> {
  return requestPhotoImport(
    `/api/v1/photo-import/sessions/${encodeURIComponent(sessionToken)}/images/${imageId}/verification`,
  );
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  return { event, data: dataLines.join("\n") };
}

/** ChatGPT-style streaming GPT read after upload (quick mode by default). */
export async function streamPhotoImportVision(
  sessionToken: string,
  imageId: number,
  mode: "quick" | "accurate" = "quick",
  handlers: PhotoImportVisionStreamHandlers,
  options?: { force?: boolean; signal?: AbortSignal },
): Promise<void> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const q = new URLSearchParams({ mode });
  if (options?.force) q.set("force", "true");
  const res = await fetch(
    `${API_BASE}/api/v1/photo-import/sessions/${encodeURIComponent(sessionToken)}/images/${imageId}/vision-stream?${q.toString()}`,
    {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: options?.signal,
    },
  );
  if (!res.ok) {
    let detail = `vision-stream failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new PhotoImportApiError(detail, res.status);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new PhotoImportApiError("No response body", 500);
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let split = buffer.indexOf("\n\n");
    while (split >= 0) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      const parsed = parseSseBlock(block);
      if (parsed) {
        try {
          const payload = JSON.parse(parsed.data) as Record<string, unknown>;
          if (parsed.event === "token" && typeof payload.text === "string") {
            handlers.onToken?.(payload.text);
          } else if (parsed.event === "status") {
            handlers.onStatus?.(payload as { phase?: string; vision_mode?: string; message?: string });
          } else if (parsed.event === "done") {
            handlers.onDone?.({
              image_id: Number(payload.image_id),
              image_status: String(payload.image_status ?? "processed"),
              reads: (payload.reads as PhotoImportVisionRead[]) ?? [],
            });
          } else if (parsed.event === "error") {
            const msg = typeof payload.message === "string" ? payload.message : "Vision read failed";
            handlers.onError?.(msg);
            throw new PhotoImportApiError(msg, 500);
          }
        } catch (err) {
          if (err instanceof PhotoImportApiError) throw err;
        }
      }
      split = buffer.indexOf("\n\n");
    }
  }
}

export async function chooseVisionReadMatch(
  readId: number,
  catalogIssueId: number,
): Promise<PhotoImportVisionRead> {
  return requestPhotoImport(`/api/v1/photo-import/vision-read/${readId}/choose-match`, {
    method: "POST",
    body: JSON.stringify({ catalog_issue_id: catalogIssueId }),
  });
}

export async function addAllSessionReads(sessionToken: string): Promise<PhotoImportAddAllResult> {
  return requestPhotoImport(
    `/api/v1/photo-import/sessions/${encodeURIComponent(sessionToken)}/add-all`,
    { method: "POST" },
  );
}

export function originalImageUrl(sessionToken: string, imageId: number): string {
  const base = API_BASE || "";
  return `${base}/api/v1/photo-import/sessions/${encodeURIComponent(sessionToken)}/images/${imageId}/original`;
}

export async function fetchVisionSandboxMetrics(): Promise<PhotoImportVisionSandboxMetrics> {
  return requestPhotoImport("/api/v1/photo-import/admin/vision-sandbox/metrics");
}
