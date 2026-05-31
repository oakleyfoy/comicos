import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ReleasePlatformPage } from "../ReleasePlatformPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title, description }: { title: string; description: string }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  ),
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("ReleasePlatformPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getReleasePlatformDashboard").mockResolvedValue({
      new_announcements: [
        {
          horizon: "ANNOUNCED",
          issue: {
            id: 1,
            release_uuid: "a",
            series_id: 1,
            issue_number: "1",
            title: "Future Spec #1",
            foc_date: null,
            release_date: "2026-09-01",
            cover_price: 5.99,
            release_status: "ANNOUNCED",
            created_at: "2026-05-30T12:00:00Z",
          },
          series: {
            id: 1,
            publisher: "Image",
            series_name: "Future Spec",
            series_type: "LIMITED",
            status: "ACTIVE",
            created_at: "2026-05-30T12:00:00Z",
          },
        },
      ],
      next_30_days: [],
      next_60_days: [],
      next_90_days: [],
      continue_run_alerts: [
        {
          plan_type: "CONTINUE_RUN",
          publisher: "Image",
          series_name: "Battle Beast",
          latest_issue_owned: "7",
          target_issue_number: "8",
          release_issue_id: 2,
          issue: {
            id: 2,
            release_uuid: "b",
            series_id: 2,
            issue_number: "8",
            title: "Battle Beast #8",
            foc_date: "2026-06-01",
            release_date: "2026-06-15",
            cover_price: 4.99,
            release_status: "SCHEDULED",
            created_at: "2026-05-30T12:00:00Z",
          },
          series: {
            id: 2,
            publisher: "Image",
            series_name: "Battle Beast",
            series_type: "ONGOING",
            status: "ACTIVE",
            created_at: "2026-05-30T12:00:00Z",
          },
        },
      ],
      start_following_alerts: [],
      new_opportunity_alerts: [
        {
          plan_type: "NEW_OPPORTUNITY",
          publisher: "Image",
          series_name: "Future Spec",
          latest_issue_owned: null,
          target_issue_number: "1",
          release_issue_id: 1,
          issue: {
            id: 1,
            release_uuid: "a",
            series_id: 1,
            issue_number: "1",
            title: "Future Spec #1",
            foc_date: null,
            release_date: "2026-09-01",
            cover_price: 5.99,
            release_status: "ANNOUNCED",
            created_at: "2026-05-30T12:00:00Z",
          },
          series: {
            id: 1,
            publisher: "Image",
            series_name: "Future Spec",
            series_type: "LIMITED",
            status: "ACTIVE",
            created_at: "2026-05-30T12:00:00Z",
          },
        },
      ],
      top_new_number_ones: [
        {
          category: "TOP_NEW_NUMBER_ONES",
          release_issue_id: 1,
          issue: {
            id: 1,
            release_uuid: "a",
            series_id: 1,
            issue_number: "1",
            title: "Future Spec #1",
            foc_date: null,
            release_date: "2026-09-01",
            cover_price: 5.99,
            release_status: "ANNOUNCED",
            created_at: "2026-05-30T12:00:00Z",
          },
          series: {
            id: 1,
            publisher: "Image",
            series_name: "Future Spec",
            series_type: "LIMITED",
            status: "ACTIVE",
            created_at: "2026-05-30T12:00:00Z",
          },
          ranking_score: 88,
          recommendation: null,
        },
      ],
      top_first_appearances: [],
      top_milestone_issues: [],
      top_variants: [],
      top_spec_opportunities: [],
      future_buy_queue: { next_30_days: [], next_60_days: [], next_90_days: [] },
      budget_forecast: {
        days_30: { must_buy: 10, strong_buy: 5, watch: 0 },
        days_60: { must_buy: 15, strong_buy: 8, watch: 2 },
        days_90: { must_buy: 20, strong_buy: 10, watch: 4 },
        expected_spend_total_30: 15,
        expected_spend_total_60: 25,
        expected_spend_total_90: 34,
      },
      variant_count: 0,
      ratio_variant_count: 0,
      cover_variant_count: 0,
      top_ratio_variants: [],
      top_new_variants: [],
    });
  });

  it("renders release platform dashboard", async () => {
    render(
      <MemoryRouter>
        <ReleasePlatformPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Release Platform" })).toBeInTheDocument();
    });

    expect(screen.getAllByText("New Announcements").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Next 30 Days").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Next 60 Days").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Next 90 Days").length).toBeGreaterThan(0);
    expect(screen.getByText("Top New #1s")).toBeInTheDocument();
    expect(screen.getByText("Top First Appearances")).toBeInTheDocument();
    expect(screen.getByText("Top Milestone Issues")).toBeInTheDocument();
    expect(screen.getByText("Top Variant Opportunities")).toBeInTheDocument();
    expect(screen.getByText("Top Spec Opportunities")).toBeInTheDocument();
    expect(screen.getByText("Continue Run Alerts")).toBeInTheDocument();
    expect(screen.getByText("Start Following")).toBeInTheDocument();
    expect(screen.getByText("New Opportunities")).toBeInTheDocument();
    expect(screen.getByText("Future Buy Queue (90 Days)")).toBeInTheDocument();
    expect(screen.getByText("Budget Forecast")).toBeInTheDocument();
  });
});
