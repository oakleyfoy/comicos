import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const PREFIX = "/api/v1/catalog-cover-hydration";

async function requestCoverHydration<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const res = await fetch(`${API_BASE}${PREFIX}${path}`, {
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

export interface CoverHydrationStatus {
  enabled: boolean;
  total: number;
  complete: number;
  failed: number;
  skipped_no_url: number;
  pending: number;
  rate_per_hour: number;
  eta_hours: number | null;
  storage_root: string;
  downloads_per_minute: number;
  year_from: number;
  year_to: number;
  total_catalog_issues: number;
  eligible_catalog_issues: number;
  asset_rows: number;
  issues_with_asset_row: number;
  queue_coverage_pct: number;
  eligible_without_asset_row: number;
  eligible_with_url_not_queued: number;
}

export function fetchCoverHydrationStatus(): Promise<CoverHydrationStatus> {
  return requestCoverHydration<CoverHydrationStatus>("/status");
}

export function runCoverHydrationDryRun(
  pilotLimit = 100,
  syncLimit = 0,
): Promise<{ report: Record<string, unknown> }> {
  return requestCoverHydration("/dry-run", {
    method: "POST",
    body: JSON.stringify({ pilot_limit: pilotLimit, sync_limit: syncLimit }),
  });
}

export function runCoverHydrationBatch(limit: number, syncLimit = 0): Promise<{ summary: Record<string, unknown> }> {
  return requestCoverHydration("/run", {
    method: "POST",
    body: JSON.stringify({ limit, sync_limit: syncLimit, confirm_write: "YES" }),
  });
}
