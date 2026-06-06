import { TOKEN_STORAGE_KEY } from "./client";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

type Envelope<T> = { data: T };

async function requestP71<T>(path: string, init?: RequestInit): Promise<T> {
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

async function requestP71Optional<T>(path: string): Promise<T | null> {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY);
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status}`);
  }
  const body = (await res.json()) as Envelope<T>;
  return body.data;
}

export type P71ExitItem = {
  title: string;
  recommendation: string;
  exit_score: number;
  exit_confidence: number;
  primary_reason: string;
};

export type P71QueueItem = {
  priority: number;
  title: string;
  recommended_action: string;
  expected_profit: number;
  target_price: number | null;
  expected_days: number;
};

export type P71ListingItem = {
  title: string;
  suggested_bin: number | null;
  listing_recommendation: string;
  expected_profit: number;
  expected_days_to_sell: number;
};

export type P71LiquidityItem = {
  title: string;
  liquidity_band: string;
  liquidity_score: number;
  days_to_sell_estimate: number;
};

export type P71Dashboard = {
  expected_realized_profit: number;
  cards_json: Record<string, unknown>;
};

export const p71Api = {
  buildPlatform: () =>
    requestP71<{ steps: unknown[] }>("/api/v1/sell-intelligence/platform/build", { method: "POST" }),
  exitRecommendations: () =>
    requestP71Optional<{ items: P71ExitItem[] }>("/api/v1/sell-intelligence/exit-recommendations"),
  exitQueue: () => requestP71Optional<{ items: P71QueueItem[] }>("/api/v1/sell-intelligence/exit-queue"),
  listingIntelligence: () =>
    requestP71Optional<{ items: P71ListingItem[] }>("/api/v1/sell-intelligence/listing-intelligence"),
  liquidity: () => requestP71Optional<{ items: P71LiquidityItem[] }>("/api/v1/sell-intelligence/liquidity"),
  dashboard: () => requestP71Optional<P71Dashboard>("/api/v1/sell-intelligence/dashboard"),
};
