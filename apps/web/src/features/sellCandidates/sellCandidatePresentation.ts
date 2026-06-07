import type { P89SellCandidateRead } from "../../api/client";

export type SellCandidateDisplayCard = {
  id: number;
  displayTitle: string;
  recommendation: P89SellCandidateRead["recommendation"];
  confidence: P89SellCandidateRead["confidence"];
  estimatedSaleValue: number;
  estimatedProfit: number;
  reasonSummary: string;
  reasons: string[];
  coverImageUrl: string;
  isTopOpportunity: boolean;
  badgeLabel: string;
  quickSalePrice: number | null;
  marketPrice: number | null;
  premiumPrice: number | null;
  pricingConfidence: string | null;
  inventoryCopyId: number;
  sellCandidateId: number;
};

const REC_LABELS: Record<P89SellCandidateRead["recommendation"], string> = {
  SELL_NOW: "Sell Now",
  HOLD: "Hold",
  GRADE_FIRST: "Grade First",
  MONITOR: "Monitor",
};

export function buildSellCandidateDisplayTitle(item: P89SellCandidateRead): string {
  if (item.issue_number) {
    return `${item.title} #${item.issue_number}`.trim();
  }
  return item.title || "Comic";
}

export function toSellCandidateDisplayCard(item: P89SellCandidateRead): SellCandidateDisplayCard {
  return {
    id: item.id,
    displayTitle: buildSellCandidateDisplayTitle(item),
    recommendation: item.recommendation,
    confidence: item.confidence,
    estimatedSaleValue: item.estimated_sale_value,
    estimatedProfit: item.estimated_profit,
    reasonSummary: item.reason_summary,
    reasons: item.reasons ?? [],
    coverImageUrl: item.cover_image_url,
    isTopOpportunity: item.is_top_opportunity,
    badgeLabel: REC_LABELS[item.recommendation],
    quickSalePrice: item.quick_sale_price ?? null,
    marketPrice: item.market_price ?? null,
    premiumPrice: item.premium_price ?? null,
    pricingConfidence: item.pricing_confidence ?? null,
    inventoryCopyId: item.inventory_copy_id,
    sellCandidateId: item.id,
  };
}

export function groupSellCandidatesByRecommendation(
  items: P89SellCandidateRead[],
): Record<P89SellCandidateRead["recommendation"], SellCandidateDisplayCard[]> {
  const groups: Record<P89SellCandidateRead["recommendation"], SellCandidateDisplayCard[]> = {
    SELL_NOW: [],
    GRADE_FIRST: [],
    HOLD: [],
    MONITOR: [],
  };
  for (const item of items) {
    groups[item.recommendation].push(toSellCandidateDisplayCard(item));
  }
  for (const key of Object.keys(groups) as (keyof typeof groups)[]) {
    groups[key].sort((a, b) => b.estimatedSaleValue - a.estimatedSaleValue);
  }
  return groups;
}
