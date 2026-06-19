import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

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
    throw new Error(detail);
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
  mobile_url: string;
  desktop_review_url: string;
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

export function createPhotoImportSession(sourceDevice?: string): Promise<PhotoImportSession> {
  return requestPhotoImport("/api/v1/photo-import/sessions", {
    method: "POST",
    body: JSON.stringify(sourceDevice ? { source_device: sourceDevice } : {}),
  });
}

export function getPhotoImportSession(token: string): Promise<PhotoImportSession> {
  return requestPhotoImport(`/api/v1/photo-import/sessions/${encodeURIComponent(token)}`);
}

export function heartbeatPhotoImportSession(token: string, sourceDevice?: string): Promise<PhotoImportSession> {
  return requestPhotoImport(`/api/v1/photo-import/sessions/${encodeURIComponent(token)}/heartbeat`, {
    method: "POST",
    body: JSON.stringify(sourceDevice ? { source_device: sourceDevice } : {}),
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
