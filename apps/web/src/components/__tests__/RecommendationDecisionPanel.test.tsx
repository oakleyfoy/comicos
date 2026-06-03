import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RecommendationDecisionPanel } from "../RecommendationDecisionPanel";
import type { RecommendationDecisionRead } from "../../api/client";

const baseDecision: RecommendationDecisionRead = {
  action: "BUY",
  quantity: 5,
      cover_recommendations: [],
  risk: "MEDIUM",
  strategy: "SELL_ONE_KEEP_ONE",
  reason_codes: ["RATIO_OPPORTUNITY", "FRANCHISE_STRENGTH"],
  reason_summary: ["Franchise strength", "Franchise strength", "FOC window"],
  expected_roi_range: "2x–3x",
  foc_date: "2026-07-12",
  release_date: "2026-08-04",
  decision_headline: "BUY 5 TOTAL",
  cover_purchase_plan: [
    {
      cover_label: "Cover A",
      recommended_quantity: 2,
      reason_codes: ["PRIMARY_COVER_LIQUIDITY"],
      reason_summary: "Primary liquidity.",
    },
    {
      cover_label: "Cover B Card Stock Variant",
      recommended_quantity: 1,
      reason_codes: ["VARIANT_DIVERSIFICATION"],
      reason_summary: "Optionality.",
    },
    {
      cover_label: "1:25",
      recommended_quantity: 2,
      reason_codes: ["RATIO_OPPORTUNITY"],
      reason_summary: "Ratio scarcity.",
    },
  ],
  quantity_reasoning: {
    base_quantity: 2,
    adjustments: [
      { label: "High confidence", delta: 1, reason_code: "HIGH_CONFIDENCE" },
      { label: "Market heat", delta: 2, reason_code: "MARKET_HEAT" },
    ],
    final_quantity: 5,
  },
  signal_matrix: {
    issue_launch: false,
    milestone_issue: true,
    first_appearance: false,
    death_or_major_event: false,
    anniversary_legacy: false,
    creator_significance: true,
    homage_cover: false,
    franchise_strength: true,
    active_collector_audience: true,
    ratio_variant_opportunity: true,
    market_heat: true,
    user_profile_match: false,
    pull_list_relevance: true,
    not_in_inventory: true,
    foc_window: true,
  },
  signal_abbreviations: [
    { key: "milestone_issue", label: "MS", description: "Milestone" },
    { key: "franchise_strength", label: "FR", description: "Franchise" },
    { key: "ratio_variant_opportunity", label: "VAR", description: "Variant" },
    { key: "foc_window", label: "FOC", description: "FOC" },
  ],
  score_breakdown: [{ label: "Franchise", points: 14, max_points: 15 }],
  top_reasons: [
    "Milestone issue detected.",
    "Strong franchise collector base.",
    "Ratio or variant opportunity present.",
  ],
  strategy_allocation_hint: "Sell 2 / Keep 3",
};

describe("RecommendationDecisionPanel", () => {
  afterEach(() => cleanup());

  it("renders BUY TOTAL and per-cover quantities", () => {
    render(<RecommendationDecisionPanel decision={baseDecision} />);
    expect(screen.getByText(/Action: BUY 5 TOTAL/i)).toBeInTheDocument();
    expect(screen.getByText(/Cover A ×2/i)).toBeInTheDocument();
    expect(screen.getByText(/1:25 ×2/i)).toBeInTheDocument();
    expect(screen.queryByText(/BUY 5 COPIES/i)).not.toBeInTheDocument();
  });

  it("renders signal abbreviations and deduped reasons", () => {
    render(<RecommendationDecisionPanel decision={baseDecision} />);
    expect(screen.getAllByText(/MS/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Milestone issue detected/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^Franchise strength$/i)).not.toBeInTheDocument();
  });

  it("renders watch monitor state without buy quantities", () => {
    const watch: RecommendationDecisionRead = {
      ...baseDecision,
      action: "WATCH",
      quantity: 0,
      cover_recommendations: [],
      cover_purchase_plan: [],
      quantity_reasoning: { base_quantity: 0, adjustments: [], final_quantity: 0 },
      strategy_allocation_hint: null,
      decision_headline: "WATCH",
    };
    render(<RecommendationDecisionPanel decision={watch} />);
    expect(screen.getByText(/Action: WATCH/i)).toBeInTheDocument();
    expect(screen.getByText(/Monitor — no purchase allocation/i)).toBeInTheDocument();
    expect(screen.queryAllByText(/Cover A ×/).length).toBe(0);
  });
});
