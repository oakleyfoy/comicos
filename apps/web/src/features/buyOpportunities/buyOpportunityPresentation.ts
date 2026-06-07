import type { P82MarketplaceAcquisitionOpportunityRead } from "../../api/client";

export type MarketplaceListingLinkInput = Pick<
  P82MarketplaceAcquisitionOpportunityRead,
  "listing_url" | "external_listing_id" | "marketplace"
>;

const SIMULATED_EXTERNAL_ID_PREFIXES = ["SIM-", "SIM-EBAY", "P82-TEST", "CERT-"] as const;

const EBAY_NUMERIC_ITEM_URL =
  /^https:\/\/(www\.)?ebay\.com\/itm\/(\d+)(\/)?(\?.*)?$/i;

function isSimulatedExternalListingId(externalListingId: string | null | undefined): boolean {
  const upper = String(externalListingId ?? "")
    .trim()
    .toUpperCase();
  if (!upper) {
    return false;
  }
  return SIMULATED_EXTERNAL_ID_PREFIXES.some((prefix) => upper.startsWith(prefix));
}

function urlContainsSimulatedToken(listingUrl: string): boolean {
  const lower = listingUrl.toLowerCase();
  return (
    lower.includes("/itm/sim-") ||
    lower.includes("sim-ebay") ||
    lower.includes("p82-test") ||
    lower.includes("cert-")
  );
}

/** No-network check: safe to show an outbound marketplace listing link. */
export function isSafeMarketplaceListingUrl(opportunity: MarketplaceListingLinkInput): boolean {
  const url = String(opportunity.listing_url ?? "").trim();
  const externalId = String(opportunity.external_listing_id ?? "").trim();

  if (!url) {
    return false;
  }
  if (isSimulatedExternalListingId(externalId)) {
    return false;
  }
  if (urlContainsSimulatedToken(url)) {
    return false;
  }
  if (EBAY_NUMERIC_ITEM_URL.test(url)) {
    return true;
  }
  if (/ebay\.com\/itm\//i.test(url)) {
    return false;
  }
  if (url.startsWith("https://")) {
    return true;
  }
  return false;
}

export type BuyOpportunityDisplayCard = {
  groupKey: string;
  displayTitle: string;
  variantLabel: string | null;
  primaryId: number;
  bestPrice: number;
  fmv: number;
  score: number;
  badgeLabel: string;
  upsideText: string;
  upsidePercent: number | null;
  reasons: string[];
  otherListingsCount: number;
  listingIds: number[];
  isTopOpportunity: boolean;
  recommendation: string;
  marketplaceLabel: string | null;
  activeListingCount: number;
  hasVerifiedListings: boolean;
  bestMarketplaceLabel: string | null;
  savingsVsHighest: number | null;
};

const RECOMMENDATION_BADGE: Record<string, string> = {
  STRONG_BUY: "Strong Buy",
  GOOD_BUY: "Strong Buy",
  SPEC_BUY: "Spec Buy",
  UNDERVALUED: "Undervalued",
  WATCH: "Watch",
  PASS: "Pass",
};

/** Lower rank = stronger buy tier for sorting. */
const RECOMMENDATION_TIER: Record<string, number> = {
  STRONG_BUY: 0,
  GOOD_BUY: 1,
  SPEC_BUY: 2,
  UNDERVALUED: 3,
  WATCH: 4,
  PASS: 5,
};

function normalizePart(value: string | null | undefined): string {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

export function formatRecommendationBadge(
  recommendation: string | null | undefined,
  score: number,
): string {
  const key = String(recommendation ?? "")
    .trim()
    .toUpperCase();
  if (key && RECOMMENDATION_BADGE[key]) {
    return RECOMMENDATION_BADGE[key];
  }
  if (key) {
    return key
      .split("_")
      .map((part) => part.charAt(0) + part.slice(1).toLowerCase())
      .join(" ");
  }
  if (score >= 85) {
    return "Strong Buy";
  }
  if (score >= 70) {
    return "Good Buy";
  }
  if (score >= 50) {
    return "Watch";
  }
  if (Number.isFinite(score) && score > 0) {
    return "Low Priority";
  }
  return "Review";
}

export function recommendationTier(recommendation: string | null | undefined): number {
  const key = String(recommendation ?? "")
    .trim()
    .toUpperCase();
  return RECOMMENDATION_TIER[key] ?? 6;
}

export function computeUpsidePercent(
  price: number | null | undefined,
  fmv: number | null | undefined,
): number | null {
  if (
    price === null ||
    price === undefined ||
    fmv === null ||
    fmv === undefined ||
    !Number.isFinite(price) ||
    !Number.isFinite(fmv) ||
    price <= 0
  ) {
    return null;
  }
  return ((fmv - price) / price) * 100;
}

export function formatUpsideDisplay(
  price: number | null | undefined,
  fmv: number | null | undefined,
): { text: string; percent: number | null } {
  const percent = computeUpsidePercent(price, fmv);
  if (percent === null) {
    return { text: "Upside: Unknown", percent: null };
  }
  if (percent <= 0) {
    if (fmv !== null && fmv !== undefined && price !== null && price !== undefined && fmv < price) {
      return { text: "Above FMV", percent };
    }
    return { text: "Upside: 0%", percent };
  }
  return { text: `Upside: +${Math.round(percent)}%`, percent };
}

function opportunityDisplayTitle(o: P82MarketplaceAcquisitionOpportunityRead): string {
  const title = o.title?.trim();
  if (title) {
    return title;
  }
  const series = o.series?.trim();
  const issue = o.issue?.trim();
  if (series && issue) {
    return `${series} #${issue}`;
  }
  return series || issue || "Untitled listing";
}

function listingFingerprint(o: P82MarketplaceAcquisitionOpportunityRead): string {
  return [
    normalizePart(o.series),
    normalizePart(o.issue),
    normalizePart(o.variant),
    normalizePart(o.title),
    Number(o.asking_price).toFixed(2),
    Number(o.estimated_fmv).toFixed(2),
    normalizePart(o.marketplace),
    normalizePart(o.external_listing_id),
  ].join("|");
}

function groupKey(o: P82MarketplaceAcquisitionOpportunityRead): string {
  return [
    normalizePart(o.series || o.title),
    normalizePart(o.issue),
    normalizePart(o.variant),
    normalizePart(o.recommendation),
  ].join("|");
}

function dedupeIdenticalListings(
  rows: P82MarketplaceAcquisitionOpportunityRead[],
): P82MarketplaceAcquisitionOpportunityRead[] {
  const seen = new Map<string, P82MarketplaceAcquisitionOpportunityRead>();
  for (const row of rows) {
    const fp = listingFingerprint(row);
    const existing = seen.get(fp);
    if (!existing || row.id < existing.id) {
      seen.set(fp, row);
    }
  }
  return [...seen.values()];
}

export function buildOpportunityReasons(
  o: P82MarketplaceAcquisitionOpportunityRead,
  otherListingsCount: number,
): string[] {
  const fromApi = (o.reasons ?? []).map((r) => String(r).trim()).filter(Boolean);
  if (fromApi.length > 0) {
    return fromApi.slice(0, 3);
  }

  const generated: string[] = [];
  if (
    Number.isFinite(o.asking_price) &&
    Number.isFinite(o.estimated_fmv) &&
    o.asking_price > 0 &&
    o.estimated_fmv > o.asking_price
  ) {
    generated.push("Listed below estimated FMV.");
  }
  const rec = String(o.recommendation ?? "").toUpperCase();
  if (rec === "GOOD_BUY" || rec === "STRONG_BUY") {
    generated.push("ComicOS flagged this as a buy candidate.");
  }
  if (o.opportunity_score >= 80) {
    generated.push("High opportunity score.");
  }
  if (otherListingsCount > 0) {
    generated.push("Multiple listings found; best price highlighted.");
  }
  return generated.slice(0, 3);
}

function marketplaceLabelFor(opportunity: P82MarketplaceAcquisitionOpportunityRead): string | null {
  if (opportunity.best_marketplace_name) {
    return opportunity.best_marketplace_name;
  }
  if (opportunity.has_verified_listings && opportunity.listing_marketplace) {
    return opportunity.listing_marketplace;
  }
  return opportunity.marketplace || null;
}

function buildCardFromListings(listings: P82MarketplaceAcquisitionOpportunityRead[]): BuyOpportunityDisplayCard {
  const sortedByPrice = [...listings].sort((a, b) => a.asking_price - b.asking_price);
  const primary = sortedByPrice[0];
  const livePrice =
    primary.has_verified_listings && primary.best_active_price != null
      ? primary.best_active_price
      : primary.asking_price;
  const bestPrice = livePrice;
  const activeListingCount = primary.active_listing_count ?? 0;
  const otherListingsCount = Math.max(0, activeListingCount - 1) || sortedByPrice.length - 1;
  const upside = formatUpsideDisplay(bestPrice, primary.estimated_fmv);
  const variant = primary.variant?.trim();
  const marketplaceLabel = marketplaceLabelFor(primary);

  return {
    groupKey: groupKey(primary),
    displayTitle: opportunityDisplayTitle(primary),
    variantLabel: variant || null,
    primaryId: primary.id,
    bestPrice,
    fmv: primary.estimated_fmv,
    score: primary.opportunity_score,
    badgeLabel: formatRecommendationBadge(primary.recommendation, primary.opportunity_score),
    upsideText: upside.text,
    upsidePercent: upside.percent,
    reasons: buildOpportunityReasons(primary, otherListingsCount),
    otherListingsCount,
    listingIds: sortedByPrice.map((l) => l.id),
    isTopOpportunity: false,
    recommendation: primary.recommendation,
    marketplaceLabel,
    activeListingCount,
    hasVerifiedListings: Boolean(primary.has_verified_listings),
    bestMarketplaceLabel: marketplaceLabel,
    savingsVsHighest:
      primary.savings_vs_highest != null && primary.savings_vs_highest > 0
        ? primary.savings_vs_highest
        : null,
  };
}

export function sortBuyOpportunityCards(cards: BuyOpportunityDisplayCard[]): BuyOpportunityDisplayCard[] {
  return [...cards].sort((a, b) => {
    const tierDiff = recommendationTier(a.recommendation) - recommendationTier(b.recommendation);
    if (tierDiff !== 0) {
      return tierDiff;
    }
    const scoreDiff = b.score - a.score;
    if (scoreDiff !== 0) {
      return scoreDiff;
    }
    const upsideA = a.upsidePercent ?? Number.NEGATIVE_INFINITY;
    const upsideB = b.upsidePercent ?? Number.NEGATIVE_INFINITY;
    if (upsideB !== upsideA) {
      return upsideB - upsideA;
    }
    return a.bestPrice - b.bestPrice;
  });
}

export function buildBuyOpportunityDisplayCards(
  items: P82MarketplaceAcquisitionOpportunityRead[],
): BuyOpportunityDisplayCard[] {
  const byGroup = new Map<string, P82MarketplaceAcquisitionOpportunityRead[]>();
  for (const item of items) {
    const key = groupKey(item);
    const bucket = byGroup.get(key) ?? [];
    bucket.push(item);
    byGroup.set(key, bucket);
  }

  const cards = [...byGroup.values()].map((groupRows) => {
    const unique = dedupeIdenticalListings(groupRows);
    return buildCardFromListings(unique);
  });

  const sorted = sortBuyOpportunityCards(cards);
  if (sorted.length > 0) {
    sorted[0] = { ...sorted[0], isTopOpportunity: true };
  }
  return sorted;
}
