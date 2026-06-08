import type { P82MarketplaceAcquisitionOpportunityRead, P90AdvisorActionRead } from "../../api/client";
import { isSafeMarketplaceListingUrl } from "./buyOpportunityPresentation";

export type BuyRecommendationType = "VERIFIED_DEAL" | "RECOMMENDED_BUY" | "WATCHLIST_BUY";

const FALSE_VERIFIED = ["verified listing", "verified marketplace listing", "live listing", "active listing"];

export type BuyTrustCheckInput = {
  has_verified_listing?: boolean;
  has_verified_listings?: boolean;
  is_verified_deal?: boolean;
  best_verified_listing?: { listing_url?: string; marketplace?: string } | null;
  action_url?: string;
  action_url_type?: string;
};

export function canShowBuyNow(item: BuyTrustCheckInput): boolean {
  if (item.is_verified_deal === false) {
    return false;
  }
  const hasFlag = Boolean(item.has_verified_listing ?? item.has_verified_listings);
  if (!hasFlag) {
    return false;
  }
  const listing = item.best_verified_listing;
  const url = (listing?.listing_url || item.action_url || "").trim();
  if (!url.startsWith("http")) {
    return false;
  }
  if (item.action_url_type && item.action_url_type !== "MARKETPLACE_LISTING") {
    return false;
  }
  return isSafeMarketplaceListingUrl({
    listing_url: url,
    external_listing_id: "",
    marketplace: listing?.marketplace ?? "EBAY",
  });
}

export function sanitizeBuyEvidence(
  action: Pick<P90AdvisorActionRead, "reason" | "primary_reason" | "supporting_signals" | "has_verified_listing">,
): { primary: string; supporting: string[] } {
  if (action.has_verified_listing) {
    return {
      primary: action.primary_reason || action.reason || "",
      supporting: [...(action.supporting_signals ?? [])].slice(0, 3),
    };
  }
  const segments = [
    ...(action.primary_reason ? [action.primary_reason] : []),
    ...(action.supporting_signals ?? []),
    ...(action.reason ? action.reason.split(" · ") : []),
  ];
  const seen = new Set<string>();
  const kept: string[] = [];
  for (const seg of segments) {
    const text = seg.replace(/\s+/g, " ").trim();
    if (!text) continue;
    const lower = text.toLowerCase();
    if (lower.includes("no verified") || lower.includes("recommendation only")) {
      if (!seen.has(lower)) {
        seen.add(lower);
        kept.push(text);
      }
      continue;
    }
    if (FALSE_VERIFIED.some((p) => lower.includes(p))) continue;
    if (lower.includes("estimated savings")) continue;
    if (seen.has(lower)) continue;
    seen.add(lower);
    kept.push(text);
  }
  const primary =
    kept.find((s) => s.toLowerCase().includes("strong buy signal")) ||
    "Strong buy signal based on collection and value data";
  const supporting = kept.filter((s) => s !== primary).slice(0, 3);
  return { primary, supporting };
}

export function advisorBuyBadge(action: P90AdvisorActionRead): string {
  const t = (action.recommendation_type || "").toUpperCase();
  if (t === "VERIFIED_DEAL" || action.is_verified_deal) return "Verified Deal";
  if (t === "WATCHLIST_BUY") return "Watch";
  return action.recommendation_type_label || "Recommended Buy";
}

export function advisorBuyMetrics(action: P90AdvisorActionRead): { label: string; value: string }[] {
  const verified = canShowBuyNow(action) || action.recommendation_type === "VERIFIED_DEAL";
  const fmv = action.estimated_value;
  if (verified) {
    const rows: { label: string; value: string }[] = [];
    if (action.current_price != null) {
      rows.push({ label: "Current Price", value: `$${action.current_price.toFixed(2)}` });
    }
    if (fmv != null) rows.push({ label: "Estimated Value", value: `$${fmv.toFixed(2)}` });
    if (action.estimated_savings != null) {
      rows.push({ label: "Estimated Savings", value: `$${action.estimated_savings.toFixed(2)}` });
    }
    if (action.potential_upside_percent != null) {
      rows.push({ label: "Discount", value: `${Math.round(action.potential_upside_percent)}%` });
    }
    return rows;
  }
  const rows: { label: string; value: string }[] = [];
  if (action.target_buy_price != null) {
    rows.push({ label: "Target Buy Price", value: `$${action.target_buy_price.toFixed(2)}` });
  }
  if (fmv != null) rows.push({ label: "Estimated Value", value: `$${fmv.toFixed(2)}` });
  if (action.potential_upside_percent != null) {
    rows.push({ label: "Potential Upside", value: `+${Math.round(action.potential_upside_percent)}%` });
  }
  return rows;
}

export function advisorValueMetricLabel(action: P90AdvisorActionRead): { label: string; amount: number } | null {
  if ((action.category || "").toUpperCase() !== "BUY") return null;
  const verified = canShowBuyNow(action);
  if (verified && action.estimated_savings != null && action.estimated_savings > 0) {
    return { label: "Estimated savings", amount: action.estimated_savings };
  }
  if (action.potential_upside_percent != null && action.potential_upside_percent > 0) {
    return { label: "Target discount", amount: action.potential_upside_percent };
  }
  if (action.potential_upside != null && action.potential_upside > 0) {
    return { label: "Potential upside", amount: action.potential_upside };
  }
  return null;
}

export function opportunityPageTitle(opp: P82MarketplaceAcquisitionOpportunityRead): string {
  if (canShowBuyNow(opp) || opp.recommendation_type === "VERIFIED_DEAL") {
    return "Verified Marketplace Deal";
  }
  return "Recommended Buy";
}

export function opportunityPriceLabel(verified: boolean): string {
  return verified ? "Current Price" : "Target Buy Price";
}
