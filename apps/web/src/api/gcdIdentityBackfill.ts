import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const PREFIX = "/api/v1/catalog-enrichment/gcd-identity-backfill";

async function requestIdentityBackfill<T>(path: string, init?: RequestInit): Promise<T> {
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

export interface GcdIdentityBackfillStatus {
  gcd_database: string;
  gcd_database_exists: boolean;
  catalog_cache: string;
  catalog_cache_exists: boolean;
  gcd_enrichment_enabled: boolean;
  max_write_batch_limit: number;
  focus_publishers: string[];
  default_year_from: number;
  default_year_to: number;
}

export interface GcdIdentityBackfillJob {
  job_id: number;
  rollback_id: number;
  source: string;
  job_type: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  total_seen: number;
  updated_issues: number;
  inserted_upcs: number;
  skipped: number;
  errors: number;
  last_error: string | null;
  scope: Record<string, unknown>;
  report: Record<string, unknown>;
  rollback: Record<string, unknown>;
}

export function fetchGcdIdentityBackfillStatus(): Promise<GcdIdentityBackfillStatus> {
  return requestIdentityBackfill<GcdIdentityBackfillStatus>(`/status`);
}

export function runGcdIdentityBackfillDryRun(body: {
  publisher?: string;
  year?: number;
  year_from?: number;
  year_to?: number;
  limit?: number;
  refresh_cache?: boolean;
  all_catalog?: boolean;
  benchmark?: boolean;
  resume_job_id?: number;
}): Promise<{ job: GcdIdentityBackfillJob }> {
  return requestIdentityBackfill(`/dry-run`, { method: "POST", body: JSON.stringify(body) });
}

export function runGcdIdentityBackfillWriteBatch(body: {
  publisher?: string;
  year?: number;
  year_from?: number;
  year_to?: number;
  limit: number;
  confirm_write: string;
  refresh_cache?: boolean;
  all_catalog?: boolean;
  resume_job_id?: number;
}): Promise<{ job: GcdIdentityBackfillJob }> {
  return requestIdentityBackfill(`/write-batch`, { method: "POST", body: JSON.stringify(body) });
}

export function fetchGcdIdentityBackfillJobs(limit = 30): Promise<{ jobs: GcdIdentityBackfillJob[] }> {
  return requestIdentityBackfill(`/jobs?limit=${limit}`);
}

export function rollbackGcdIdentityBackfillJob(jobId: number): Promise<Record<string, unknown>> {
  return requestIdentityBackfill(`/jobs/${jobId}/rollback`, { method: "POST" });
}
