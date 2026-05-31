import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, type ReleaseVariantRead } from "../../api/client";
import { ReleaseIntelligencePage } from "../ReleaseIntelligencePage";
import { ReleasePlatformPage } from "../ReleasePlatformPage";
import { SpecIntelligencePage } from "../SpecIntelligencePage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => (
    <header>
      <h1>{title}</h1>
    </header>
  ),
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

export const sampleVariant: ReleaseVariantRead = {
  id: 100,
  issue_id: 5,
  variant_uuid: "lunar-variant-zatanna-5-a",
  variant_name: "Cover A",
  ratio_value: null,
  ratio_type: null,
  is_incentive_variant: false,
  variant_type: "COVER",
  cover_artist: null,
  source_item_code: "012345678901",
  created_at: "2026-05-30T12:00:00Z",
};

export const sampleRatioVariant: ReleaseVariantRead = {
  id: 101,
  issue_id: 5,
  variant_uuid: "lunar-variant-zatanna-5-inc25",
  variant_name: "Cover D 1:25",
  ratio_value: 25,
  ratio_type: "INC",
  is_incentive_variant: true,
  variant_type: "RATIO",
  cover_artist: null,
  source_item_code: "012345678902",
  created_at: "2026-05-30T12:00:00Z",
};

describe("Variant dashboard sections", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders variant metrics on Release Intelligence", async () => {
    vi.spyOn(apiClient, "getReleaseIntelligenceDashboard").mockResolvedValue({
      upcoming_releases: [],
      foc_calendar: [],
      new_number_one_feed: [],
      key_issue_feed: [],
      variant_feed: [],
      agent_activity: [],
      variant_count: 4,
      ratio_variant_count: 1,
      cover_variant_count: 3,
      recent_variants: [sampleVariant, sampleRatioVariant],
      top_ratio_variants: [sampleRatioVariant],
    });

    render(
      <MemoryRouter>
        <ReleaseIntelligencePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("4")).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "Recent Variants" })).toBeInTheDocument();
    expect(screen.getByText("Cover A")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recent Ratio Variants" })).toBeInTheDocument();
    expect(screen.getAllByText("Cover D 1:25").length).toBeGreaterThan(0);
  });

  it("renders variant metrics on Release Platform", async () => {
    vi.spyOn(apiClient, "getReleasePlatformDashboard").mockResolvedValue({
      new_announcements: [],
      next_30_days: [],
      next_60_days: [],
      next_90_days: [],
      continue_run_alerts: [],
      start_following_alerts: [],
      new_opportunity_alerts: [],
      top_new_number_ones: [],
      top_first_appearances: [],
      top_milestone_issues: [],
      top_variants: [],
      top_spec_opportunities: [],
      future_buy_queue: { next_30_days: [], next_60_days: [], next_90_days: [] },
      budget_forecast: {
        days_30: { must_buy: 0, strong_buy: 0, watch: 0 },
        days_60: { must_buy: 0, strong_buy: 0, watch: 0 },
        days_90: { must_buy: 0, strong_buy: 0, watch: 0 },
        expected_spend_total_30: 0,
        expected_spend_total_60: 0,
        expected_spend_total_90: 0,
      },
      variant_count: 2,
      ratio_variant_count: 1,
      cover_variant_count: 1,
      top_ratio_variants: [sampleRatioVariant],
      top_new_variants: [sampleVariant],
    });

    render(
      <MemoryRouter>
        <ReleasePlatformPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Recent Ratio Variants" })).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "Recent Variants" })).toBeInTheDocument();
    expect(screen.getByText("1:25")).toBeInTheDocument();
  });

  it("renders variant metrics on Spec Intelligence", async () => {
    vi.spyOn(apiClient, "getSpecIntelligenceDashboard").mockResolvedValue({
      top_spec_opportunities: [],
      weekly_buy_lists: [],
      new_number_one_opportunities: [],
      variant_opportunities: [],
      key_issue_opportunities: [],
      watch_opportunities: [],
      recommendation_reviews: [],
      agent_activity: [],
      variant_count: 5,
      ratio_variant_count: 2,
      top_ratio_variants: [sampleRatioVariant],
      upcoming_incentive_variants: [sampleRatioVariant],
    });

    render(
      <MemoryRouter>
        <SpecIntelligencePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Upcoming Incentive Variants" })).toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "Top Variant Opportunities" })).toBeInTheDocument();
    expect(screen.getAllByText("5").length).toBeGreaterThan(0);
  });
});
