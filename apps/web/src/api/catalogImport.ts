import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const PREFIX = "/api/v1/catalog-import";

async function requestCatalogImport<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
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

export interface GcdImportStatus {
  gcd_database: string;
  gcd_database_exists: boolean;
  catalog_cache: string;
  catalog_cache_exists: boolean;
  gcd_import_enabled: boolean;
  max_write_batch_limit: number;
  focus_publishers: string[];
  default_year_from: number;
  default_year_to: number;
}

export interface GcdImportCellStats {
  publisher: string;
  year: number;
  gcd_rows: number;
  existing_issues: number;
  clean_candidates: number;
  variants: number;
  reprints: number;
  foreign_editions: number;
  conflicts: number;
  low_confidence: number;
  barcodes_available: number;
  estimated_scan_seconds: number;
  estimated_write_seconds: number;
}

export interface GcdImportMatrixResponse {
  generated_at: string;
  year_from: number;
  year_to: number;
  elapsed_seconds: number;
  job_id: number | null;
  cells: GcdImportCellStats[];
}

export interface GcdImportScopeResponse {
  publisher: string;
  year: number;
  elapsed_seconds: number;
  job_id?: number | null;
  stats: GcdImportCellStats;
  preview_rows: Record<string, unknown>[];
}

export interface GcdImportJob {
  job_id: number;
  rollback_id: number;
  source: string;
  job_type: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  total_seen: number;
  inserted_issues: number;
  inserted_upcs: number;
  skipped: number;
  errors: number;
  last_error: string | null;
  scope: Record<string, unknown>;
  scope_stats: Record<string, unknown>;
  report: Record<string, unknown>;
  rollback: Record<string, unknown>;
}

export function fetchGcdImportStatus(): Promise<GcdImportStatus> {
  return requestCatalogImport<GcdImportStatus>(`${PREFIX}/gcd/status`);
}

export function fetchGcdImportMatrix(body: {
  year_from: number;
  year_to: number;
  refresh_cache?: boolean;
}): Promise<GcdImportMatrixResponse> {
  return requestCatalogImport<GcdImportMatrixResponse>(`${PREFIX}/gcd/matrix`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchGcdImportScope(params: {
  publisher: string;
  year: number;
  preview_limit?: number;
  refresh_cache?: boolean;
}): Promise<GcdImportScopeResponse> {
  const q = new URLSearchParams({
    publisher: params.publisher,
    year: String(params.year),
    preview_limit: String(params.preview_limit ?? 100),
    refresh_cache: String(params.refresh_cache ?? false),
  });
  return requestCatalogImport<GcdImportScopeResponse>(`${PREFIX}/gcd/scope?${q}`);
}

export function gcdImportScopeCsvUrl(params: { publisher: string; year: number; preview_limit?: number }): string {
  const q = new URLSearchParams({
    publisher: params.publisher,
    year: String(params.year),
    preview_limit: String(params.preview_limit ?? 100),
  });
  return `${API_BASE}${PREFIX}/gcd/scope.csv?${q}`;
}

export function runGcdImportDryRun(body: {
  publisher: string;
  year: number;
  preview_limit?: number;
  refresh_cache?: boolean;
}): Promise<{ job: GcdImportJob }> {
  return requestCatalogImport<{ job: GcdImportJob }>(`${PREFIX}/gcd/dry-run`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function runGcdImportWriteBatch(body: {
  publisher: string;
  year: number;
  limit: number;
  confirm_write: string;
  refresh_cache?: boolean;
}): Promise<{ job: GcdImportJob }> {
  return requestCatalogImport<{ job: GcdImportJob }>(`${PREFIX}/gcd/write-batch`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchGcdImportJobs(limit = 30): Promise<{ jobs: GcdImportJob[] }> {
  return requestCatalogImport<{ jobs: GcdImportJob[] }>(`${PREFIX}/jobs?limit=${limit}`);
}

export function fetchGcdImportJob(jobId: number): Promise<{ job: GcdImportJob }> {
  return requestCatalogImport<{ job: GcdImportJob }>(`${PREFIX}/jobs/${jobId}`);
}

export function rollbackGcdImportJob(jobId: number): Promise<Record<string, unknown>> {
  return requestCatalogImport<Record<string, unknown>>(`${PREFIX}/jobs/${jobId}/rollback`, { method: "POST" });
}
