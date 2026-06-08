import type { P90AdvisorActionRead } from "../../api/client";
import type { P82MarketplaceAcquisitionOpportunityRead } from "../../api/client";
import { isSafeMarketplaceListingUrl } from "./buyOpportunityPresentation";
import { canShowBuyNow, type BuyTrustCheckInput } from "./buyRecommendationTrust";

export type BuyActionUrlType = "MARKETPLACE_LISTING" | "OPPORTUNITY_DETAIL" | "MARKETPLACE_SEARCH";

export type BuyCta = {
  label: string;
  href: string;
  external: boolean;
  subtext: string;
  urlType: BuyActionUrlType;
};

export function opportunityHasVerifiedListing(opp: BuyTrustCheckInput): boolean {
  return canShowBuyNow(opp);
}

export function resolveOpportunityBuyCta(
  opp: P82MarketplaceAcquisitionOpportunityRead,
  options?: { multipleVerified?: boolean },
): BuyCta {
  const verified = opportunityHasVerifiedListing(opp);
  const listingUrl = opp.best_verified_listing?.listing_url?.trim();
  const marketplaceName =
    opp.best_verified_listing?.marketplace_name ||
    opp.best_marketplace_name ||
    opp.listing_marketplace ||
    opp.marketplace ||
    "marketplace";

  if (verified && listingUrl) {
    return {
      label: "Buy Now",
      href: listingUrl,
      external: true,
      subtext: `Verified listing on ${marketplaceName}`,
      urlType: "MARKETPLACE_LISTING",
    };
  }

  const searchTitle = opp.title?.trim() || `${opp.series ?? ""} ${opp.issue ?? ""}`.trim();
  return {
    label: searchTitle ? "Search Marketplaces" : "Review Opportunity",
    href: searchTitle ? `/buy-opportunities?search=${encodeURIComponent(searchTitle)}` : `/marketplace-opportunity/${opp.id}`,
    external: false,
    subtext: "No verified live listing is currently available.",
    urlType: searchTitle ? "MARKETPLACE_SEARCH" : "OPPORTUNITY_DETAIL",
  };
}

export function resolveAdvisorBuyCta(
  action: Pick<
    P90AdvisorActionRead,
    | "category"
    | "action_route"
    | "action_url"
    | "action_url_type"
    | "has_verified_listing"
    | "marketplace_name"
    | "entity_id"
  > &
    Partial<Pick<P90AdvisorActionRead, "comic" | "display_label" | "reason" | "confidence" | "priority_score">>,
): BuyCta {
  const urlType = (action.action_url_type || "OPPORTUNITY_DETAIL") as BuyActionUrlType;
  const url = (action.action_url || action.action_route || "").trim();

  if (canShowBuyNow(action) && urlType === "MARKETPLACE_LISTING" && url.startsWith("http")) {
    return {
      label: "Buy Now",
      href: url,
      external: true,
      subtext: action.marketplace_name
        ? `Verified marketplace listing on ${action.marketplace_name}`
        : "Verified marketplace listing",
      urlType: "MARKETPLACE_LISTING",
    };
  }

  return {
    label: "Review Opportunity",
    href: url.startsWith("/") ? url : `/marketplace-opportunity/${action.entity_id ?? ""}`,
    external: false,
    subtext: "Recommendation only · no verified listing yet",
    urlType: urlType === "MARKETPLACE_SEARCH" ? "MARKETPLACE_SEARCH" : "OPPORTUNITY_DETAIL",
  };
}

export function recommendationHeaderLabel(
  opp: P82MarketplaceAcquisitionOpportunityRead,
): string {
  if (opportunityHasVerifiedListing(opp)) {
    const rec = String(opp.recommendation ?? "").toUpperCase();
    if (rec === "STRONG_BUY" || rec === "GOOD_BUY") {
      return "Strong Buy";
    }
    return "Buy Opportunity";
  }
  return "Recommended Buy";
}
