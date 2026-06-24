import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class GptComicReadApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "GptComicReadApiError";
    this.status = status;
  }
}

export type GptComicReadBarcodeRead = {
  barcode: string | null;
  barcode_type: string | null;
  confidence: number;
  method: "local_decode" | "gpt_barcode_read" | "none";
  crop_used: string | null;
  error: string | null;
};

export type GptComicReadCatalogMatch = {
  matched: boolean;
  catalog_issue_id?: number | null;
  method?: string;
  confidence?: number | null;
  series?: string | null;
  issue_number?: string | null;
  publisher?: string | null;
  cover_image_url?: string | null;
  alternates?: Array<Record<string, unknown>>;
};

export type GptComicReadComicvineMatch = {
  matched: boolean;
  source: string;
  comicvine_issue_id?: string | null;
  series?: string | null;
  issue_number?: string | null;
  publisher?: string | null;
  cover_date?: string | null;
  name?: string | null;
  image_url?: string | null;
  raw?: Record<string, unknown> | null;
};

export type GptComicReadGptFields = {
  publisher: string;
  series: string;
  issue_number: string | null;
  issue_title: string;
  year: string;
  cover_date: string;
  variant_description: string;
  barcode: string;
  confidence: number;
  reasoning: string;
  possible_alternates: string[];
  raw_response: Record<string, unknown>;
  model: string;
  image_width: number;
  image_height: number;
};

export type GptComicReadResult = {
  gpt_read: GptComicReadGptFields;
  catalog_match: GptComicReadCatalogMatch;
  barcode_read: GptComicReadBarcodeRead;
  comicvine_barcode_match: GptComicReadComicvineMatch;
  final_match_source: "comicvine_barcode" | "catalog" | "gpt_only";
};

export function finalMatchSourceLabel(source: GptComicReadResult["final_match_source"]): string {
  if (source === "comicvine_barcode") return "Barcode verified";
  if (source === "catalog") return "Catalog match";
  return "GPT only";
}

export function barcodeMethodLabel(method: GptComicReadBarcodeRead["method"]): string {
  if (method === "local_decode") return "Local decode";
  if (method === "gpt_barcode_read") return "GPT barcode crop";
  return "None";
}

export async function readComicWithGpt(file: File): Promise<GptComicReadResult> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const form = new FormData();
  form.append("image", file);
  const res = await fetch(`${API_BASE}/api/v1/gpt-comic-read`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    let detail = `GPT comic read failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new GptComicReadApiError(detail, res.status);
  }
  return (await res.json()) as GptComicReadResult;
}
