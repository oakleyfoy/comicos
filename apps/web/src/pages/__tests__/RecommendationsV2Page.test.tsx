import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { RecommendationsV2Page } from "../RecommendationsV2Page";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const mockDashboard = {
  must_buy: [{ id: 1, release_issue_id: 1, release_variant_id: null, series_name: "TMNT", issue_number: "1", title: "TMNT #1", publisher: "IDW", total_score: 88, recommendation_tier: "MUST_BUY", recommendation_type: "INVESTMENT_NUMBER_ONE", confidence_score: 0.9 }],
  strong_buy: [],
  buy: [],
  watch: [],
  pass_tier: [],
  investment_number_ones: [],
  start_run: [],
  key_issues: [],
  ratio_variants: [],
  user_preference_matches: [],
};

describe("RecommendationsV2Page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "postRecommendationsV2Run").mockResolvedValue({
      run_uuid: "run-1",
      status: "COMPLETED",
      issues_scored: 10,
      variants_scored: 2,
      recommendations_created: 12,
    });
    vi.spyOn(apiClient, "getRecommendationsV2Dashboard").mockResolvedValue(mockDashboard);
  });

  it("renders recommendation tiers", async () => {
    render(
      <MemoryRouter>
        <RecommendationsV2Page />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Recommendations V2" })).toBeInTheDocument();
    });
    expect(screen.getByText("Must Buy")).toBeInTheDocument();
    expect(screen.getByText(/TMNT/)).toBeInTheDocument();
  });
});
