import { describe, expect, it } from "vitest";

import { isSafeMarketplaceListingUrl } from "../buyOpportunityPresentation";
import { opportunityHasVerifiedListing, resolveAdvisorBuyCta, resolveOpportunityBuyCta } from "../buyVerifiedAction";

describe("buyVerifiedAction", () => {
  it("shows Buy Now only with verified listing URL", () => {
    const opp = {
      id: 1,
      marketplace: "EBAY",
      external_listing_id: "123",
      listing_url: "",
      title: "Absolute Batman #20",
      publisher: "",
      series: "Absolute Batman",
      issue: "20",
      variant: "",
      asking_price: 4.49,
      estimated_fmv: 10,
      discount_to_fmv: 55,
      liquidity: 0,
      velocity: 0,
      grading_upside: 0,
      ownership_status: "",
      profile_match_score: 0,
      opportunity_score: 90,
      recommendation: "STRONG_BUY",
      reasons: [],
      status: "ACTIVE",
      created_at: "",
      updated_at: "",
      has_verified_listings: true,
      best_verified_listing: {
        marketplace: "EBAY",
        marketplace_name: "eBay",
        listing_url: "https://www.ebay.com/itm/1234567890",
        price: 4.49,
        total_cost: 4.49,
      },
    };
    expect(opportunityHasVerifiedListing(opp)).toBe(true);
    const cta = resolveOpportunityBuyCta(opp);
    expect(cta.label).toBe("Buy Now");
    expect(cta.external).toBe(true);
  });

  it("uses Review/Search when no verified listing", () => {
    const opp = {
      id: 2,
      marketplace: "EBAY",
      external_listing_id: "SIM-EBAY-1",
      listing_url: "https://www.ebay.com/itm/sim-1",
      title: "Energon Universe #2026SPECIAL1",
      publisher: "",
      series: "",
      issue: "",
      variant: "",
      asking_price: 5,
      estimated_fmv: 10,
      discount_to_fmv: 50,
      liquidity: 0,
      velocity: 0,
      grading_upside: 0,
      ownership_status: "",
      profile_match_score: 0,
      opportunity_score: 80,
      recommendation: "GOOD_BUY",
      reasons: [],
      status: "ACTIVE",
      created_at: "",
      updated_at: "",
      has_verified_listings: false,
      best_verified_listing: null,
    };
    expect(isSafeMarketplaceListingUrl(opp)).toBe(false);
    const cta = resolveOpportunityBuyCta(opp);
    expect(cta.label).not.toBe("Buy Now");
    expect(cta.subtext).toMatch(/No verified live listing/i);
  });

  it("advisor card Buy Now for MARKETPLACE_LISTING", () => {
    const cta = resolveAdvisorBuyCta({
      category: "BUY",
      comic: "Absolute Batman #20",
      display_label: "Absolute Batman #20",
      reason: "55% below estimated value",
      confidence: "HIGH",
      priority_score: 89,
      action_url: "https://www.ebay.com/itm/1234567890",
      action_route: "/marketplace-opportunity/1",
      action_url_type: "MARKETPLACE_LISTING",
      has_verified_listing: true,
      marketplace_name: "eBay",
    });
    expect(cta.label).toBe("Buy Now");
    expect(cta.external).toBe(true);
  });

  it("advisor card Review without verified listing", () => {
    const cta = resolveAdvisorBuyCta({
      category: "BUY",
      comic: "Absolute Batman #20",
      display_label: "Absolute Batman #20",
      reason: "Recommendation",
      confidence: "MEDIUM",
      priority_score: 50,
      action_url: "/marketplace-opportunity/1",
      action_route: "/marketplace-opportunity/1",
      action_url_type: "OPPORTUNITY_DETAIL",
      has_verified_listing: false,
    });
    expect(cta.label).toBe("Review");
  });
});
