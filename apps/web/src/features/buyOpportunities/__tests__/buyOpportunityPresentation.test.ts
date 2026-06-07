import { describe, expect, it } from "vitest";

import type { P82MarketplaceAcquisitionOpportunityRead } from "../../api/client";
import {
  buildBuyOpportunityDisplayCards,
  formatRecommendationBadge,
  formatUpsideDisplay,
  isSafeMarketplaceListingUrl,
} from "../buyOpportunityPresentation";

function opp(
  partial: Partial<P82MarketplaceAcquisitionOpportunityRead> & { id: number },
): P82MarketplaceAcquisitionOpportunityRead {
  return {
    marketplace: "ebay",
    external_listing_id: `ext-${partial.id}`,
    listing_url: "",
    title: "Energon Universe #2026SPECIAL1",
    publisher: "",
    series: "Energon Universe",
    issue: "2026SPECIAL1",
    variant: "",
    asking_price: 3.2,
    estimated_fmv: 10,
    discount_to_fmv: 0,
    liquidity: 0,
    velocity: 0,
    grading_upside: 0,
    ownership_status: "",
    profile_match_score: 0,
    opportunity_score: 81,
    recommendation: "GOOD_BUY",
    reasons: [],
    status: "OPEN",
    created_at: "",
    updated_at: "",
    ...partial,
  };
}

describe("buyOpportunityPresentation", () => {
  it("maps GOOD_BUY to Strong Buy and never exposes raw enum", () => {
    expect(formatRecommendationBadge("GOOD_BUY", 81)).toBe("Strong Buy");
    expect(formatRecommendationBadge("GOOD_BUY", 81)).not.toMatch(/GOOD_BUY/);
  });

  it("formats upside when price and FMV exist", () => {
    expect(formatUpsideDisplay(3.2, 10).text).toBe("Upside: +213%");
  });

  it("dedupes identical listings into one card", () => {
    const cards = buildBuyOpportunityDisplayCards([
      opp({ id: 1, external_listing_id: "a" }),
      opp({ id: 2, external_listing_id: "a" }),
    ]);
    expect(cards).toHaveLength(1);
    expect(cards[0].otherListingsCount).toBe(0);
  });

  it("groups same book with different prices and shows best price plus other count", () => {
    const cards = buildBuyOpportunityDisplayCards([
      opp({ id: 1, asking_price: 5 }),
      opp({ id: 2, asking_price: 3.2, external_listing_id: "b" }),
      opp({ id: 3, asking_price: 4.5, external_listing_id: "c" }),
    ]);
    expect(cards).toHaveLength(1);
    expect(cards[0].bestPrice).toBe(3.2);
    expect(cards[0].otherListingsCount).toBe(2);
  });

  it("marks exactly one top opportunity", () => {
    const cards = buildBuyOpportunityDisplayCards([
      opp({ id: 1, opportunity_score: 70, recommendation: "WATCH" }),
      opp({
        id: 2,
        title: "Absolute Batman #20",
        series: "Absolute Batman",
        issue: "20",
        opportunity_score: 90,
        recommendation: "STRONG_BUY",
      }),
    ]);
    expect(cards.filter((c) => c.isTopOpportunity)).toHaveLength(1);
    expect(cards[0].isTopOpportunity).toBe(true);
    expect(cards[0].displayTitle).toContain("Absolute Batman");
  });

  it("keeps different variants as separate cards", () => {
    const cards = buildBuyOpportunityDisplayCards([
      opp({ id: 1, variant: "A" }),
      opp({ id: 2, variant: "B", external_listing_id: "b" }),
    ]);
    expect(cards).toHaveLength(2);
  });

  describe("isSafeMarketplaceListingUrl", () => {
    it("rejects simulated and test external listing IDs", () => {
      expect(
        isSafeMarketplaceListingUrl({
          listing_url: "https://www.ebay.com/itm/SIM-EBAY-P82-1",
          external_listing_id: "SIM-EBAY-P82-1",
          marketplace: "EBAY",
        }),
      ).toBe(false);
      expect(
        isSafeMarketplaceListingUrl({
          listing_url: "https://www.ebay.com/itm/P82-TEST-1",
          external_listing_id: "P82-TEST-1",
          marketplace: "EBAY",
        }),
      ).toBe(false);
      expect(
        isSafeMarketplaceListingUrl({
          listing_url: "https://www.ebay.com/itm/CERT-P82-001",
          external_listing_id: "CERT-P82-001",
          marketplace: "EBAY",
        }),
      ).toBe(false);
    });

    it("allows numeric eBay item URLs", () => {
      expect(
        isSafeMarketplaceListingUrl({
          listing_url: "https://www.ebay.com/itm/123456789012",
          external_listing_id: "123456789012",
          marketplace: "EBAY",
        }),
      ).toBe(true);
    });

    it("rejects empty URLs", () => {
      expect(
        isSafeMarketplaceListingUrl({
          listing_url: "",
          external_listing_id: "123",
          marketplace: "EBAY",
        }),
      ).toBe(false);
    });
  });
});
