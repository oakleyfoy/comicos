import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class IntakeApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "IntakeApiError";
    this.status = status;
  }
}

async function requestIntake<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new IntakeApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export type IntakeSession = {
  id: number;
  session_token: string;
  name: string | null;
  status: string;
  source_device: string | null;
  scanned_count: number;
  acquisition_id: number | null;
  acquisition_label: string | null;
  created_at: string;
  expires_at: string;
  last_seen_at: string | null;
  scanner_url: string;
  review_url: string;
};

export type IntakeCounts = {
  scanned: number;
  queued: number;
  processing: number;
  auto_matched: number;
  ready_for_review: number;
  needs_review: number;
  needs_full_cover_photo: number;
  added_to_inventory: number;
  rejected: number;
  failed: number;
};

export type IntakeItemCandidate = {
  id: number;
  catalog_issue_id: number | null;
  variant_id: number | null;
  publisher: string | null;
  series: string | null;
  issue_number: string | null;
  cover_url: string | null;
  score: number;
  source: string | null;
  rank: number;
};

export type IntakeItem = {
  id: number;
  session_id: number;
  status: string;
  confidence: number;
  match_source: string | null;
  raw_barcode: string | null;
  normalized_barcode: string | null;
  base_upc: string | null;
  extension: string | null;
  possible_corrected_barcode: string | null;
  barcode_read: Record<string, unknown> | null;
  selected_catalog_issue_id: number | null;
  selected_variant_id: number | null;
  matched_publisher: string | null;
  matched_series: string | null;
  matched_issue_number: string | null;
  matched_year: string | null;
  cover_url: string | null;
  reason: string | null;
  error: string | null;
  image_url: string;
  acquisition_id: number | null;
  inventory_copy_id: number | null;
  created_at: string;
  processed_at: string | null;
  candidates: IntakeItemCandidate[];
};

export type IntakeReview = {
  session: IntakeSession;
  counts: IntakeCounts;
  items: IntakeItem[];
};

export function intakeImageUrl(item: IntakeItem): string {
  return `${API_BASE}${item.image_url}`;
}

export function createIntakeSession(input: {
  acquisition_id: number;
  source_device?: string;
  name?: string;
}): Promise<IntakeSession> {
  return requestIntake<IntakeSession>("/api/v1/intake/sessions", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getIntakeSession(token: string): Promise<IntakeSession> {
  return requestIntake<IntakeSession>(`/api/v1/intake/sessions/${token}`);
}

export function setIntakeSessionStatus(
  token: string,
  newStatus: "active" | "paused" | "stopped",
): Promise<IntakeSession> {
  return requestIntake<IntakeSession>(`/api/v1/intake/sessions/${token}/status`, {
    method: "POST",
    body: JSON.stringify({ status: newStatus }),
  });
}

export function getIntakeCounts(token: string): Promise<IntakeCounts> {
  return requestIntake<IntakeCounts>(`/api/v1/intake/sessions/${token}/counts`);
}

export async function enqueueIntakeItem(
  token: string,
  blob: Blob,
  rawBarcode?: string,
  extraFrames?: Blob[],
): Promise<{ item_id: number; status: string; scanned_count: number }> {
  const form = new FormData();
  form.append("file", blob, "scan.jpg");
  if (rawBarcode) form.append("raw_barcode", rawBarcode);
  for (let i = 0; i < (extraFrames?.length ?? 0); i += 1) {
    const frame = extraFrames?.[i];
    if (frame) form.append("frame_files", frame, `frame_${i}.jpg`);
  }
  return requestIntake(`/api/v1/intake/sessions/${token}/items`, {
    method: "POST",
    body: form,
  });
}

export function getIntakeReview(token: string, statusFilter?: string): Promise<IntakeReview> {
  const query = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
  return requestIntake<IntakeReview>(`/api/v1/intake/sessions/${token}/review${query}`);
}

export function acceptIntakeItem(itemId: number): Promise<IntakeItem> {
  return requestIntake<IntakeItem>(`/api/v1/intake/items/${itemId}/accept`, { method: "POST" });
}

export function chooseIntakeItemIssue(
  itemId: number,
  catalogIssueId: number,
  variantId?: number | null,
): Promise<IntakeItem> {
  return requestIntake<IntakeItem>(`/api/v1/intake/items/${itemId}/choose`, {
    method: "POST",
    body: JSON.stringify({ catalog_issue_id: catalogIssueId, variant_id: variantId ?? null }),
  });
}

export function addIntakeItemToInventory(itemId: number): Promise<IntakeItem> {
  return requestIntake<IntakeItem>(`/api/v1/intake/items/${itemId}/add-to-inventory`, {
    method: "POST",
  });
}

export function importAndAcceptIntakeItem(itemId: number): Promise<IntakeItem> {
  return requestIntake<IntakeItem>(`/api/v1/intake/items/${itemId}/import-and-accept`, {
    method: "POST",
  });
}

export type IntakeCatalogSearchResult = {
  catalog_issue_id: number;
  series: string | null;
  issue_number: string | null;
  publisher: string | null;
  cover_url: string | null;
};

export function searchCatalogIssues(
  q: string,
  issueNumber?: string,
): Promise<{ results: IntakeCatalogSearchResult[] }> {
  const params = new URLSearchParams({ q });
  if (issueNumber) params.set("issue_number", issueNumber);
  return requestIntake(`/api/v1/intake/catalog-search?${params.toString()}`);
}

export function rejectIntakeItem(itemId: number): Promise<IntakeItem> {
  return requestIntake<IntakeItem>(`/api/v1/intake/items/${itemId}/reject`, { method: "POST" });
}

export function requeueIntakeItem(itemId: number, fullCoverRequired?: boolean): Promise<IntakeItem> {
  const query =
    fullCoverRequired === true ? "?full_cover_required=true" : "";
  return requestIntake<IntakeItem>(`/api/v1/intake/items/${itemId}/requeue${query}`, {
    method: "POST",
  });
}

export async function uploadIntakeFullCoverPhoto(itemId: number, blob: Blob): Promise<IntakeItem> {
  const form = new FormData();
  form.append("file", blob, "full_cover.jpg");
  return requestIntake<IntakeItem>(`/api/v1/intake/items/${itemId}/full-cover-photo`, {
    method: "POST",
    body: form,
  });
}

export function addAllHighConfidence(
  token: string,
): Promise<{ added: number; candidates: number; skipped?: string[] }> {
  return requestIntake(`/api/v1/intake/sessions/${token}/add-all-high-confidence`, {
    method: "POST",
  });
}
