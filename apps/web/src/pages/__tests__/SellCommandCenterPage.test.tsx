import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import * as clientModule from "../../api/client";
import { SellCommandCenterPage } from "../SellCommandCenterPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const payload: clientModule.P89SellCommandCenterRead = {
  status: "OK",
  kpis: {
    sell_now_count: 2,
    grade_first_count: 1,
    drafts_awaiting_review: 3,
    active_listings: 1,
    sold_this_month: 2,
    estimated_net_profit: 120,
  },
  daily_actions: [
    {
      rank: 1,
      title: "Review 2 SELL NOW candidates",
      detail: "Top opportunities.",
      action_label: "Review Sell Candidates",
      route: "/sell-candidates",
      urgency_score: 150,
    },
  ],
  sell_now: [
    {
      sell_candidate_id: 1,
      comic_title: "Spider-Man #300",
      sell_score: 92,
      estimated_sale_value: 400,
      estimated_profit: 200,
      confidence: "HIGH",
      reason_summary: "Strong sell signal",
      cta_label: "Review Sell Candidate",
      cta_route: "/sell-candidates",
    },
  ],
  grade_first: [
    {
      sell_candidate_id: 2,
      comic_title: "X-Men #1",
      grade_first_score: 80,
      estimated_sale_value: 300,
      potential_upside: 50,
      confidence: "MEDIUM",
      reason_summary: "Grade first",
      cta_label: "Review Grading Candidate",
      cta_route: "/sell-candidates",
    },
  ],
  hold_or_monitor: [],
  drafts_needing_review: [
    {
      draft_id: 5,
      comic_title: "Batman #423",
      marketplace: "EBAY",
      suggested_price: 75,
      created_at: "2026-06-01T00:00:00Z",
      cta_route: "/listing-drafts/5",
    },
  ],
  active_listings: [
    {
      listing_id: 9,
      comic_title: "Hulk #181",
      marketplace: "EBAY",
      asking_price: 500,
      minimum_price: 450,
      listed_at: "2026-05-01T00:00:00Z",
      days_listed: 35,
      needs_review: true,
      cta_route: "/listing-management/9",
    },
  ],
  sold_recently: [
    {
      listing_id: 3,
      comic_title: "ASM #129",
      sale_price: 180,
      net_profit: 90,
      profit_known: true,
      sold_at: "2026-06-04T00:00:00Z",
      cta_route: "/listing-management/3",
    },
  ],
  expired_or_stale: [],
  profit_summary: {
    period_label: "Current month",
    gross_sales: 500,
    fees: 50,
    shipping_costs: 20,
    net_profit: 180,
    average_profit_per_sale: 90,
    sold_count: 2,
  },
  quick_actions: [{ label: "Open Sell Candidates", route: "/sell-candidates", action_type: "SELL_CANDIDATES" }],
  briefing_summary: {
    top_sell_candidate: "Spider-Man #300",
    top_grade_first_candidate: "X-Men #1",
    drafts_awaiting_review: 3,
    active_listings: 1,
    sold_this_month: 2,
    net_profit_this_month: 180,
  },
  generated_at: "2026-06-08T00:00:00Z",
};

describe("SellCommandCenterPage", () => {
  it("renders KPI bar and main sections", async () => {
    vi.spyOn(clientModule.apiClient, "getSellCommandCenter").mockResolvedValue(payload);
    render(
      <MemoryRouter>
        <SellCommandCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Sell Command Center" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sell Now", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Grade First Before Selling", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Listing drafts needing review", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Active listings", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sold recently", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Profit summary", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Spider-Man #300")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Daily seller actions", level: 2 })).toBeInTheDocument();
  });

  it("renders empty sections copy", async () => {
    vi.spyOn(clientModule.apiClient, "getSellCommandCenter").mockResolvedValue({
      ...payload,
      sell_now: [],
      grade_first: [],
      drafts_needing_review: [],
      active_listings: [],
      sold_recently: [],
      daily_actions: [],
    });
    render(
      <MemoryRouter>
        <SellCommandCenterPage />
      </MemoryRouter>,
    );
    expect(await screen.findByText("No SELL NOW candidates cached.")).toBeInTheDocument();
    expect(screen.getByText("No grade-first candidates.")).toBeInTheDocument();
  });
});
