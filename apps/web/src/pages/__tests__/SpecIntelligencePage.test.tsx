import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { SpecIntelligencePage } from "../SpecIntelligencePage";

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

describe("SpecIntelligencePage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getSpecIntelligenceDashboard").mockResolvedValue({
      top_spec_opportunities: [
        {
          id: 1,
          recommendation_uuid: "spec-rec-1",
          release_issue_id: 10,
          recommendation_type: "STRONG_BUY",
          recommendation_score: 88,
          confidence_score: 0.92,
          recommendation_reason: "Signals + preferences",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      weekly_buy_lists: [
        {
          weekly_buy_list: {
            id: 1,
            owner_user_id: 1,
            list_uuid: "list-1",
            week_start_date: "2026-05-25",
            generated_at: "2026-05-30T12:00:00Z",
          },
          items: [
            {
              id: 1,
              weekly_buy_list_id: 1,
              release_issue_id: 10,
              buy_category: "Must Buy",
              ranking_score: 88,
              created_at: "2026-05-30T12:00:00Z",
            },
            {
              id: 2,
              weekly_buy_list_id: 1,
              release_issue_id: 11,
              buy_category: "Watch",
              ranking_score: 52,
              created_at: "2026-05-30T12:00:00Z",
            },
          ],
        },
      ],
      new_number_one_opportunities: [
        {
          id: 2,
          recommendation_uuid: "spec-rec-2",
          release_issue_id: 11,
          recommendation_type: "BUY",
          recommendation_score: 72,
          confidence_score: 0.86,
          recommendation_reason: "NEW_NUMBER_ONE",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      variant_opportunities: [
        {
          id: 3,
          recommendation_uuid: "spec-rec-3",
          release_issue_id: 12,
          recommendation_type: "WATCH",
          recommendation_score: 51,
          confidence_score: 0.79,
          recommendation_reason: "VARIANT_RATIO",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      key_issue_opportunities: [
        {
          id: 4,
          recommendation_uuid: "spec-rec-4",
          release_issue_id: 13,
          recommendation_type: "BUY",
          recommendation_score: 67,
          confidence_score: 0.84,
          recommendation_reason: "FIRST_APPEARANCE",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      watch_opportunities: [
        {
          id: 5,
          recommendation_uuid: "spec-rec-5",
          release_issue_id: 14,
          recommendation_type: "WATCH",
          recommendation_score: 49,
          confidence_score: 0.73,
          recommendation_reason: "Preference match",
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      recommendation_reviews: [
        {
          id: 1,
          recommendation_id: 1,
          review_status: "REVIEWED",
          reviewed_at: "2026-05-30T12:30:00Z",
          review_notes: "Looks good",
        },
      ],
      agent_activity: [
        {
          id: 1,
          owner_user_id: 1,
          agent_code: "weekly_buy_list",
          execution_uuid: "exec-1",
          status: "COMPLETED",
          started_at: "2026-05-30T12:00:00Z",
          completed_at: "2026-05-30T12:00:01Z",
          duration_ms: 24,
          created_at: "2026-05-30T12:00:00Z",
        },
      ],
      variant_count: 0,
      ratio_variant_count: 0,
      top_ratio_variants: [],
      upcoming_incentive_variants: [],
    });
  });

  it("renders spec intelligence dashboard", async () => {
    render(
      <MemoryRouter>
        <SpecIntelligencePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Spec Intelligence" })).toBeInTheDocument();
    });

    expect(screen.getAllByText("Must Buy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Strong Buy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Watch").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Pass").length).toBeGreaterThan(0);
    expect(screen.getByText("Weekly Buy List")).toBeInTheDocument();
    expect(screen.getByText("Top Spec Opportunities")).toBeInTheDocument();
    expect(screen.getByText("Variant Opportunities")).toBeInTheDocument();
    expect(screen.getByText("New #1 Opportunities")).toBeInTheDocument();
    expect(screen.getByText("Key Issue Opportunities")).toBeInTheDocument();
    expect(screen.getByText("Recommendation Reviews")).toBeInTheDocument();
    expect(screen.getByText("Agent Activity")).toBeInTheDocument();
  });
});
