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

export type GptComicReadResult = {
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
