import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const NAV_TIMEOUT_MS = 25_000;

type Envelope<T> = { data: T };

type WithStatus = { status?: string; message?: string };

async function requestP67<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), NAV_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
    let envelope: Envelope<T & WithStatus>;
    try {
      envelope = (await res.json()) as Envelope<T & WithStatus>;
    } catch {
      throw new Error(`${path} returned an invalid response (${res.status})`);
    }
    if (!res.ok) {
      const msg =
        (envelope as { error?: { message?: string } }).error?.message ??
        envelope.data?.message ??
        `${path} failed (${res.status})`;
      throw new Error(msg);
    }
    const data = envelope.data;
    if (data?.status === "ERROR") {
      throw new Error(data.message || `${path} failed`);
    }
    return data;
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(`${path} timed out after ${NAV_TIMEOUT_MS / 1000}s`);
    }
    throw err;
  } finally {
    window.clearTimeout(timer);
  }
}

export type P67BuildResult<T> = { ok: true; data: T } | { ok: false; error: string; data: T | null };

async function requestP67Build<T extends WithStatus>(path: string): Promise<P67BuildResult<T>> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), NAV_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    const envelope = (await res.json()) as Envelope<T>;
    const data = envelope.data;
    if (!res.ok) {
      return {
        ok: false,
        error: (envelope as { error?: { message?: string } }).error?.message ?? `Build failed (${res.status})`,
        data: data ?? null,
      };
    }
    if (data?.status === "ERROR") {
      return { ok: false, error: data.message || "Build failed", data };
    }
    return { ok: true, data };
  } catch (err) {
    const message =
      err instanceof Error && err.name === "AbortError"
        ? `Build timed out after ${NAV_TIMEOUT_MS / 1000}s`
        : err instanceof Error
          ? err.message
          : "Build failed";
    return { ok: false, error: message, data: null };
  } finally {
    window.clearTimeout(timer);
  }
}

export type P67PortfolioLatest = {
  snapshot: {
    total_cost_basis: number;
    total_estimated_value: number;
    total_unrealized_gain: number;
    total_unrealized_gain_pct: number;
    average_roi_pct: number;
    best_performer_title: string;
    worst_performer_title: string;
    metadata_json: Record<string, unknown>;
  } | null;
  items: Array<{ title: string; roi_pct: number; estimated_value: number; cost_basis: number }>;
};

export type P67CollectionLatest = {
  status?: string;
  message?: string;
  total_holdings: number;
  concentration_score: number;
  metadata_json: Record<string, unknown>;
};

export type P67RecommendationLatest = {
  snapshot: {
    hit_rate_pct: number;
    average_return_pct: number;
    recommendation_roi_pct: number;
    confidence_accuracy_pct: number;
  } | null;
  items: Array<{ title: string; outcome: string; return_pct: number }>;
};

export type P67GradingLatest = {
  snapshot: { total_candidates: number } | null;
  items: Array<{ title: string; estimated_roi_pct: number; submission_priority: number }>;
};

export type P67InvestorLatest = {
  status?: string;
  message?: string;
  collection_value: number;
  cost_basis: number;
  unrealized_gain: number;
  realized_gain: number;
  portfolio_health_score: number;
  cards_json: Record<string, unknown>;
};

export type P68SnapshotRow = {
  title: string;
  blended_fmv: number | null;
  confidence: number;
  sales_count: number;
  liquidity_score: number;
  low_sale: number | null;
  median_sale: number | null;
  high_sale: number | null;
  primary_provider: string;
  price_trend_30d: string;
  metadata_json: Record<string, unknown>;
};

export type P68SnapshotsLatest = {
  status?: string;
  message?: string;
  items: P68SnapshotRow[];
  total: number;
};

export type P68SnapshotsBuild = {
  status?: string;
  message?: string;
  built: number;
  items: P68SnapshotRow[];
};

export const p68Api = {
  buildSnapshots: () =>
    requestP67Build<P68SnapshotsBuild>("/api/v1/market-pricing/snapshots/build"),
  latestSnapshots: () => requestP67<P68SnapshotsLatest>("/api/v1/market-pricing/snapshots/latest"),
};

export const p67Api = {
  buildPlatform: () =>
    requestP67Build<{ status?: string; message?: string; steps: unknown[]; certification: { certified: boolean } }>(
      "/api/v1/portfolio-analytics/platform/build",
    ),
  portfolioLatest: () => requestP67<P67PortfolioLatest>("/api/v1/portfolio-analytics/latest"),
  collectionLatest: () => requestP67<P67CollectionLatest>("/api/v1/collection-analytics/latest"),
  recommendationLatest: () => requestP67<P67RecommendationLatest>("/api/v1/recommendation-performance/latest"),
  gradingLatest: () => requestP67<P67GradingLatest>("/api/v1/grading-analytics/latest"),
  investorLatest: () => requestP67<P67InvestorLatest>("/api/v1/investor-dashboard/latest"),
};
