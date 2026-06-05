import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type Envelope<T> = { data: T };

async function requestP67<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new Error(`${path} failed: ${res.status}`);
  }
  const body = (await res.json()) as Envelope<T>;
  return body.data;
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

export const p68Api = {
  buildSnapshots: () =>
    requestP67<{ built: number; items: P68SnapshotRow[] }>("/api/v1/market-pricing/snapshots/build", { method: "POST" }),
  latestSnapshots: () => requestP67<{ items: P68SnapshotRow[]; total: number }>("/api/v1/market-pricing/snapshots/latest"),
};

export const p67Api = {
  buildPlatform: () => requestP67<{ steps: unknown[]; certification: { certified: boolean } }>("/api/v1/portfolio-analytics/platform/build", { method: "POST" }),
  portfolioLatest: () => requestP67<P67PortfolioLatest>("/api/v1/portfolio-analytics/latest"),
  collectionLatest: () => requestP67<P67CollectionLatest>("/api/v1/collection-analytics/latest"),
  recommendationLatest: () => requestP67<P67RecommendationLatest>("/api/v1/recommendation-performance/latest"),
  gradingLatest: () => requestP67<P67GradingLatest>("/api/v1/grading-analytics/latest"),
  investorLatest: () => requestP67<P67InvestorLatest>("/api/v1/investor-dashboard/latest"),
};
