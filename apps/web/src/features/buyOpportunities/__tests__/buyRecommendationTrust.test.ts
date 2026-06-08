import { describe, expect, it } from "vitest";

import type { P90AdvisorActionRead } from "../../api/client";
import {
  advisorBuyBadge,
  advisorValueMetricLabel,
  canShowBuyNow,
  sanitizeBuyEvidence,
} from "../buyRecommendationTrust";

describe("buyRecommendationTrust", () => {
  it("does not allow Buy Now without verified safe listing", () => {
    expect(
      canShowBuyNow({
        has_verified_listing: false,
        is_verified_deal: false,
      }),
    ).toBe(false);
  });

  it("uses Target discount label for recommendation-only advisor rows", () => {
    const action = {
      category: "BUY",
      has_verified_listing: false,
      potential_upside_percent: 55,
    } as P90AdvisorActionRead;
    expect(advisorValueMetricLabel(action)?.label).toBe("Target discount");
  });

  it("uses Estimated savings only for verified deals", () => {
    const action = {
      category: "BUY",
      has_verified_listing: true,
      is_verified_deal: true,
      action_url: "https://www.ebay.com/itm/1234567890",
      action_url_type: "MARKETPLACE_LISTING",
      estimated_savings: 5.51,
      best_verified_listing: {
        marketplace: "EBAY",
        listing_url: "https://www.ebay.com/itm/1234567890",
        price: 4.49,
        total_cost: 4.49,
      },
    } as P90AdvisorActionRead;
    expect(advisorBuyBadge(action)).toBe("Verified Deal");
    expect(advisorValueMetricLabel(action)?.label).toBe("Estimated savings");
  });

  it("strips verified listing copy when unverified", () => {
    const cleaned = sanitizeBuyEvidence({
      reason: "55% below FMV · verified listing",
      primary_reason: "55% below FMV",
      supporting_signals: ["verified listing"],
      has_verified_listing: false,
    });
    expect(cleaned.supporting.join(" ").toLowerCase()).not.toContain("verified listing");
  });
});
